"""HM-10 BLE transport with motor commands, active brake, and optional UART telemetry.

Tkinter never runs on this BLE event-loop thread; status changes pass through Queue.
"""
from __future__ import annotations

import asyncio
import queue
import threading
import time

from motor_control import parse_telemetry

try:
    from bleak import BleakScanner, BleakClient
    BLEAK_ERROR = None
except ImportError as exc:
    BleakScanner = BleakClient = None
    BLEAK_ERROR = str(exc)


# A blocked Windows BLE write must not stall the entire control loop forever.
GATT_WRITE_TIMEOUT_S = 0.85
DRIVE_STREAM_INTERVAL_S = 0.12
BRAKE_STREAM_INTERVAL_S = 0.30


class BLEBridge:
    def __init__(self):
        self.events = queue.Queue()
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._thread_main, daemon=True)
        self.thread.start()
        self.client = None
        self.char = None
        self.write_response = False
        self.stream_task = None
        self._lock = threading.Lock()
        self._motor = (0, 0)
        self._brake = True  # fail-safe: link must start braking
        self._emergency_latched = False
        self._updated = time.monotonic()
        self._rx_partial = bytearray()
        self._tx_count = 0
        self._last_tx_report = 0.0
        self._write_lock = asyncio.Lock()
        self._probe_waiting = False
        self._closing = False

    def _thread_main(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_forever()
        finally:
            # Keep the asynchronous transport from leaking Windows BLE resources.
            pending = asyncio.all_tasks(self.loop)
            for task in pending:
                task.cancel()
            if pending:
                self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            self.loop.close()

    def _schedule(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def set_motor(self, left, right):
        with self._lock:
            # The Arduino X latch requires an explicit U + zero frame rearm.
            # Never enqueue movement while the software E-stop is latched.
            if getattr(self, '_emergency_latched', False):
                return
            self._motor = (int(max(-255, min(255, left))), int(max(-255, min(255, right))))
            self._brake = False
            self._updated = time.monotonic()

    def set_brake(self):
        with self._lock:
            already_braking = self._brake
            self._motor = (0, 0)
            self._brake = True
            self._updated = time.monotonic()
        # Push a brake immediately rather than waiting for periodic streaming.
        # Stream rechecks the brake state before every write.
        if not already_braking and self.client is not None and self.char is not None:
            self._schedule(self._urgent_brake())

    def latch_emergency(self):
        """Latch Arduino emergency stop (v1.6.5+), with old K-brake fallback."""
        self.set_brake()
        with self._lock:
            self._emergency_latched = True
        if self.client is not None and self.char is not None:
            self._schedule(self._send_emergency_latch())

    async def _send_emergency_latch(self):
        if not self.client or not self.client.is_connected or not self.char:
            return
        try:
            async with self._write_lock:
                # Send ordinary K first for compatibility with v1.6.4.
                await asyncio.wait_for(
                    self.client.write_gatt_char(self.char, b'K\n', response=self.write_response),
                    timeout=GATT_WRITE_TIMEOUT_S)
                await asyncio.wait_for(
                    self.client.write_gatt_char(self.char, b'X\n', response=self.write_response),
                    timeout=GATT_WRITE_TIMEOUT_S)
            self.events.put(('info', 'Emergency stop latched; re-arm explicitly'))
        except Exception as exc:
            self.events.put(('error', f'Emergency stop write failed: {exc}; cut motor battery power'))

    def release_emergency(self):
        """Explicit manual arm: unlatch X and send a zero/brake frame first."""
        if self.client is not None and self.client.is_connected and self.char is not None:
            self._schedule(self._release_emergency())

    async def _release_emergency(self):
        if not self.client or not self.client.is_connected or not self.char:
            return
        try:
            async with self._write_lock:
                with self._lock:
                    self._motor = (0, 0)
                    self._brake = True
                    self._updated = time.monotonic()
                await asyncio.wait_for(
                    self.client.write_gatt_char(self.char, b'U\n', response=self.write_response),
                    timeout=GATT_WRITE_TIMEOUT_S)
                await asyncio.wait_for(
                    self.client.write_gatt_char(self.char, b'M,0,0\n', response=self.write_response),
                    timeout=GATT_WRITE_TIMEOUT_S)
                with self._lock:
                    self._emergency_latched = False
            self.events.put(('info', 'Motor arm sequence sent; wheels remain braked until new input'))
        except Exception as exc:
            with self._lock:
                self._emergency_latched = True
                self._brake = True
                self._motor = (0, 0)
            self.events.put(('error', f'Cannot re-arm motors: {exc}'))

    async def _urgent_brake(self):
        if self.client is not None and self.client.is_connected and self.char is not None:
            try:
                # _send rechecks the live state after acquiring the write lock.
                # An old emergency task must not brake a later *new* key press.
                await self._send(brake=True)
            except Exception as exc:
                self.events.put(('error', f'Immediate brake write failed: {exc}'))

    def scan(self):
        if BLEAK_ERROR:
            self.events.put(('error', 'Install BLE dependency: py -m pip install -r requirements.txt'))
            return
        self._schedule(self._scan())

    async def _scan(self):
        self.events.put(('scan_started', 'BLE scan started (6 seconds)'))
        self.events.put(('info', 'Scanning nearby Bluetooth Low Energy devices...'))
        try:
            found = await BleakScanner.discover(timeout=6.0)
            found = sorted(found, key=lambda d: (not bool(d.name), (d.name or '').lower()))
            self.events.put(('devices', found))
        except Exception as exc:
            self.events.put(('scan_failed', str(exc)))
            self.events.put(('error', f'BLE scan failed: {exc}'))

    def connect(self, device, characteristic_uuid):
        if BLEAK_ERROR:
            self.events.put(('error', 'Bleak not installed. Run run.bat first.'))
            return
        self._schedule(self._connect(device, characteristic_uuid))

    async def _connect(self, device, characteristic_uuid):
        if self.client and self.client.is_connected:
            self.events.put(('error', 'Disconnect first before changing devices.'))
            return
        self.events.put(('link_progress', f'Connecting to {device.name or device.address}...'))
        self.events.put(('info', f'Connecting to {device.name or device.address}...'))
        client = BleakClient(device, disconnected_callback=self._on_disconnect)
        try:
            await client.connect(timeout=15.0)
            self.events.put(('link_progress', 'BLE link established; discovering GATT services'))
            desired = characteristic_uuid.lower().strip()
            if len(desired) == 4 and all(c in '0123456789abcdef' for c in desired):
                desired = f'0000{desired}-0000-1000-8000-00805f9b34fb'
            chars = [char for svc in client.services for char in svc.characteristics]
            self.events.put(('gatt_inventory', [(c.uuid, list(c.properties)) for c in chars]))
            target = next((char for char in chars if char.uuid.lower() == desired), None)
            if not target:
                choices = [char.uuid for char in chars if
                           'write' in char.properties or 'write-without-response' in char.properties]
                raise RuntimeError('UART characteristic not found. Writable UUIDs: ' + ', '.join(choices))
            if 'write-without-response' not in target.properties and 'write' not in target.properties:
                raise RuntimeError('Selected GATT characteristic is not writable.')
            self.write_response = 'write-without-response' not in target.properties
            self.events.put(('gatt_ok', {'uuid': target.uuid, 'properties': list(target.properties),
                                         'write_mode': 'with response' if self.write_response else 'without response'}))
            self.client = client
            self.char = target
            self._tx_count = 0
            self._rx_partial.clear()
            if 'notify' in target.properties:
                try:
                    await client.start_notify(target, self._notification)
                    self.events.put(('notify_ok', f'Notifications subscribed on {target.uuid}'))
                    self.events.put(('telemetry_state', 'WAITING FOR ARDUINO'))
                except Exception as exc:
                    self.events.put(('notify_failed', str(exc)))
                    self.events.put(('telemetry_state', 'NOTIFICATIONS FAILED'))
                    self.events.put(('info', f'BLE connected, but no notifications: {exc}'))
            else:
                self.events.put(('notify_failed', 'Selected characteristic does not support notify'))
                self.events.put(('telemetry_state', 'NOTIFY UNSUPPORTED'))
            # Never connect in coast mode or with stale drive data. Send active
            # brake before declaring the link ready or starting the stream.
            self.set_brake()
            await self._send(brake=True)
            # A new connection must not clear a previous firmware E-stop.
            # Latch until the user explicitly arms after verifying safety.
            await self._send_emergency_latch()
            with self._lock:
                self._emergency_latched = True
            self.stream_task = asyncio.create_task(self._stream())
            self.events.put(('connected', device.name or device.address))
        except Exception as exc:
            self.events.put(('connect_failed', str(exc)))
            self.events.put(('error', f'Connection failed: {exc}'))
            self.client = None
            self.char = None
            try:
                if client.is_connected:
                    await client.disconnect()
            except Exception:
                pass

    def _notification(self, _sender, data):
        """BLE notifications may split or combine UART lines; reassemble safely."""
        self._rx_partial.extend(bytes(data))
        if len(self._rx_partial) > 120:
            # Keep the newest complete frame in the buffer after corrupted traffic.
            last_newline = self._rx_partial.rfind(b'\n')
            self._rx_partial = self._rx_partial[last_newline + 1:] if last_newline != -1 else bytearray()
        while b'\n' in self._rx_partial:
            line, _, rest = self._rx_partial.partition(b'\n')
            self._rx_partial = bytearray(rest)
            message = line.decode('ascii', errors='ignore').strip()
            if message == 'H,13':
                self.events.put(('firmware_reply', ('1.3', time.monotonic())))
                continue
            parsed = parse_telemetry(message)
            if parsed:
                self.events.put(('telemetry', (parsed, time.monotonic())))
            elif message:
                self.events.put(('unknown_reply', message[:80]))

    def _on_disconnect(self, _client):
        self.set_brake()
        self.events.put(('lost', 'Bluetooth connection closed'))

    async def _send(self, left=0, right=0, brake=False):
        """Write latest desired state; never transmit a stale snapshot.

        The asyncio write lock is shared by stream, urgent brake and probes.
        Refreshing state *inside* it prevents a delayed earlier send from
        briefly overwriting a new key press or releasing an active brake.
        """
        async with self._write_lock:
            with self._lock:
                left, right = self._motor
                now_braking = self._brake
                age = time.monotonic() - self._updated
            # A queued immediate-brake request from an earlier release must
            # not override a new explicit motor command made since then.
            if brake and not now_braking:
                return
            if age > 0.90:
                now_braking = True
            payload = b'K\n' if now_braking else f'M,{left},{right}\n'.encode('ascii')
            t0 = time.monotonic()
            try:
                await asyncio.wait_for(
                    self.client.write_gatt_char(self.char, payload, response=self.write_response),
                    timeout=GATT_WRITE_TIMEOUT_S)
            except asyncio.TimeoutError as exc:
                raise RuntimeError(
                    f'BLE GATT write stalled (> {GATT_WRITE_TIMEOUT_S:.2f}s). '
                    'Motor commands may be lost; stopping link.') from exc
            self.events.put(('tx_frame', {
                'sent_at': time.monotonic(),
                'frame': payload.decode('ascii').strip(),
                'latency_ms': (time.monotonic() - t0) * 1000.0,
                'intent_age_ms': age * 1000.0,
            }))

    async def _stream(self):
        try:
            while self.client and self.client.is_connected:
                # _send computes current state only once it gets the lock.
                await self._send()
                self._tx_count += 1
                if time.monotonic() - self._last_tx_report > 0.5:
                    self.events.put(('write_ok', self._tx_count))
                    self.events.put(('tx_stats', self._tx_count))
                    self._last_tx_report = time.monotonic()
                with self._lock:
                    moving = not self._brake and self._motor != (0, 0)
                # Fewer idle writes, but refresh active motor commands often.
                await asyncio.sleep(DRIVE_STREAM_INTERVAL_S if moving else BRAKE_STREAM_INTERVAL_S)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            with self._lock:
                self._brake = True  # fail closed; cannot rely on the disconnected BLE link
                self._motor = (0, 0)
            self.events.put(('write_failed', str(exc)))
            self.events.put(('error', f'BLE write failed: {exc}'))
            try:
                if self.client and self.client.is_connected:
                    await self.client.disconnect()
            except Exception:
                pass

    def probe_firmware(self):
        """Non-driving handshake probe. Old v1.2 firmware will not answer Q."""
        if self.client is not None and self.client.is_connected and self.char is not None:
            self._schedule(self._probe_firmware())
        else:
            self.events.put(('probe_error', 'No connected writable BLE characteristic'))

    async def _probe_firmware(self):
        try:
            # Retry briefly to mitigate a lost SoftwareSerial / BLE UART packet.
            for attempt in range(3):
                if not self.client or not self.client.is_connected:
                    raise RuntimeError('BLE link disappeared before handshake')
                async with self._write_lock:
                    await asyncio.wait_for(
                        self.client.write_gatt_char(self.char, b'Q\n', response=self.write_response),
                        timeout=GATT_WRITE_TIMEOUT_S)
                self.events.put(('probe_sent', attempt + 1))
                await asyncio.sleep(0.4)
        except Exception as exc:
            self.events.put(('probe_error', str(exc)))

    def disconnect(self):
        self.set_brake()
        self._schedule(self._disconnect())

    async def _disconnect(self):
        client = self.client
        if not client:
            self.events.put(('disconnected', 'Disconnected'))
            return
        try:
            if client.is_connected and self.char:
                await self._send(brake=True)
            if self.stream_task:
                self.stream_task.cancel()
                try:
                    await self.stream_task
                except asyncio.CancelledError:
                    pass
            if client.is_connected:
                await client.disconnect()
        except Exception as exc:
            self.events.put(('error', f'Disconnect warning: {exc}'))
        finally:
            self.client = None
            self.char = None
            self.stream_task = None
            self.events.put(('disconnected', 'Disconnected'))

    def close(self):
        """Orderly nonblocking shutdown: send brake and disconnect before ending BLE loop."""
        if self._closing:
            return
        self._closing = True
        self.set_brake()
        self._schedule(self._close())

    async def _close(self):
        try:
            await self._disconnect()
        finally:
            self.loop.call_soon(self.loop.stop)
