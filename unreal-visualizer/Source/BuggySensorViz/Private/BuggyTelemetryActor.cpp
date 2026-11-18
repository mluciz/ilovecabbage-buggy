#include "BuggyTelemetryActor.h"
#include "Sockets.h"
#include "SocketSubsystem.h"
#include "Common/UdpSocketBuilder.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonReader.h"
#include "Dom/JsonObject.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/StaticMesh.h"
#include "Engine/Engine.h"
#include "UObject/ConstructorHelpers.h"
#include "HAL/PlatformTime.h"

ABuggyTelemetryActor::ABuggyTelemetryActor()
{
    PrimaryActorTick.bCanEverTick = true;
    SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    RootComponent = SceneRoot;
    BuggyMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Buggy"));
    BuggyMesh->SetupAttachment(SceneRoot);
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
    if (Cube.Succeeded()) BuggyMesh->SetStaticMesh(Cube.Object);
    BuggyMesh->SetRelativeScale3D(FVector(0.28, 0.18, 0.12));
    BuggyMesh->SetRelativeLocation(FVector(0, 0, 8));
    BuggyMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
}
void ABuggyTelemetryActor::BeginPlay()
{
    Super::BeginPlay();
    Socket = FUdpSocketBuilder(TEXT("BuggyVizTelemetry"))
        .AsNonBlocking().AsReusable().BoundToAddress(FIPv4Address::InternalLoopback)
        .BoundToPort(ListenPort).WithReceiveBufferSize(256 * 1024);
    if (!Socket) UE_LOG(LogTemp, Error, TEXT("BuggyViz UDP port %d unavailable"), ListenPort);
}
void ABuggyTelemetryActor::EndPlay(const EEndPlayReason::Type Reason)
{
    if (Socket) { Socket->Close(); ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->DestroySocket(Socket); Socket = nullptr; }
    Super::EndPlay(Reason);
}
void ABuggyTelemetryActor::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
    // Cap processing to prevent a high-volume producer from freezing the game thread.
    if (Socket)
    {
        uint32 BytesPending = 0;
        for (int32 Index = 0; Index < 32 && Socket->HasPendingData(BytesPending); ++Index)
        {
            TArray<uint8> Bytes;
            Bytes.SetNumUninitialized(FMath::Min(BytesPending, (uint32)4096));
            int32 BytesRead = 0;
            if (!Socket->Recv(Bytes.GetData(), Bytes.Num(), BytesRead) || BytesRead <= 0) break;
            FUTF8ToTCHAR Utf8(reinterpret_cast<const ANSICHAR*>(Bytes.GetData()), BytesRead);
            ApplyPacket(FString(Utf8.Length(), Utf8.Get()), DeltaTime);
        }
    }
    const double Now = FPlatformTime::Seconds();
    for (int32 i = Observations.Num() - 1; i >= 0; --i)
    {
        if (Now - Observations[i].Time > ObstaclePersistenceSeconds)
        {
            if (Observations[i].Actor.IsValid()) Observations[i].Actor->Destroy();
            Observations.RemoveAtSwap(i);
        }
    }
    if (GEngine)
    {
        const bool bConnected = LastPacketAt >= 0 && Now - LastPacketAt < 2.0;
        const FString Status = FString::Printf(TEXT("BuggyViz %s | packets %d | range %.0f mm (%s) | yaw %.1f deg | obstacles %d"),
            bConnected ? TEXT("RECEIVING") : TEXT("STALE / NO DATA"), AcceptedPacketCount, LastRangeMm,
            bLastRangeValid ? TEXT("valid") : TEXT("invalid"), EstimatedYawDegrees, Observations.Num());
        GEngine->AddOnScreenDebugMessage(91743, 0.0f, bConnected ? FColor::Green : FColor::Yellow, Status);
    }
}
void ABuggyTelemetryActor::ApplyPacket(const FString& Payload, float DeltaTime)
{
    if (Payload.Len() > 4096) return;
    TSharedPtr<FJsonObject> Data;
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Payload);
    if (!FJsonSerializer::Deserialize(Reader, Data) || !Data.IsValid()) return;
    double Version = 0;
    if (!Data->TryGetNumberField(TEXT("schema"), Version) || Version != 1) return;

    // Pose is optional. Do not integrate accelerometer into position: drift would be severe.
    const TSharedPtr<FJsonObject>* Pose = nullptr;
    if (Data->TryGetObjectField(TEXT("pose"), Pose))
    {
        double X=0, Y=0, Yaw=0;
        if ((*Pose)->TryGetNumberField(TEXT("x_m"), X) && (*Pose)->TryGetNumberField(TEXT("y_m"), Y) &&
            FMath::IsFinite(X) && FMath::IsFinite(Y) && FMath::Abs(X) < 100 && FMath::Abs(Y) < 100)
            SetActorLocation(FVector(X * 100.0, Y * 100.0, 0.0));
        if ((*Pose)->TryGetNumberField(TEXT("yaw_deg"), Yaw) && FMath::IsFinite(Yaw))
            EstimatedYawDegrees = FMath::UnwindDegrees((float)Yaw);
    }
    else
    {
        // Yaw-only fallback is dead-reckoning and will drift.
        const TSharedPtr<FJsonObject>* Imu = nullptr;
        if (Data->TryGetObjectField(TEXT("imu"), Imu))
        {
            double GyroZ = 0, Dt = 0;
            if ((*Imu)->TryGetNumberField(TEXT("gyro_z_dps"), GyroZ) &&
                (*Imu)->TryGetNumberField(TEXT("dt_s"), Dt) && Dt > 0 && Dt < 0.2 && FMath::Abs(GyroZ) < 2000)
                EstimatedYawDegrees = FMath::UnwindDegrees(EstimatedYawDegrees + (float)(GyroZ * Dt));
        }
    }
    SetActorRotation(FRotator(0, EstimatedYawDegrees, 0));

    const TSharedPtr<FJsonObject>* Tof = nullptr;
    if (Data->TryGetObjectField(TEXT("tof"), Tof))
    {
        double Range=0, SensorYaw=0;
        bool bValid=false;
        (*Tof)->TryGetBoolField(TEXT("valid"), bValid);
        if ((*Tof)->TryGetNumberField(TEXT("distance_mm"), Range) && FMath::IsFinite(Range))
        {
            LastRangeMm = (float)Range;
            bLastRangeValid = bValid && Range > 0 && Range <= MaximumAcceptedDistanceMm;
            (*Tof)->TryGetNumberField(TEXT("sensor_yaw_deg"), SensorYaw);
            if (bLastRangeValid && FMath::IsFinite(SensorYaw)) AddRangeObservation((float)Range, (float)SensorYaw);
        }
    }
    LastPacketAt = FPlatformTime::Seconds();
    ++AcceptedPacketCount;
}
void ABuggyTelemetryActor::AddRangeObservation(float RangeMm, float SensorYawDegrees)
{
    const double Now = FPlatformTime::Seconds();
    if (LastObservationAt >= 0 && Now - LastObservationAt < 0.12) return;
    LastObservationAt = Now;
    if (Observations.Num() >= 160) return;
    UWorld* World = GetWorld();
    if (!World) return;
    const float YawRad = FMath::DegreesToRadians(EstimatedYawDegrees + SensorYawDegrees);
    const FVector Direction(FMath::Cos(YawRad), FMath::Sin(YawRad), 0.0f);
    // Position is an observation point, not a reconstructed obstacle volume.
    const FVector Hit = GetActorLocation() + Direction * (RangeMm * 0.1f + 15.0f) + FVector(0, 0, 12);
    AStaticMeshActor* Marker = World->SpawnActor<AStaticMeshActor>(Hit, FRotator::ZeroRotator);
    if (!Marker) return;
    static UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
    Marker->GetStaticMeshComponent()->SetStaticMesh(Cube);
    Marker->GetStaticMeshComponent()->SetWorldScale3D(FVector(0.04f));
    Marker->GetStaticMeshComponent()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Observations.Add({Marker, Now});
}
