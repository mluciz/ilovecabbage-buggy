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
#include "Materials/MaterialInterface.h"
#include "Engine/DirectionalLight.h"
#include "Components/DirectionalLightComponent.h"
#include "Engine/World.h"
#include "DrawDebugHelpers.h"
#include "UObject/ConstructorHelpers.h"
#include "HAL/PlatformTime.h"
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "HAL/PlatformFileManager.h"
#include "Misc/DateTime.h"

namespace
{
    static const FColor SensorColors[3] = {
        FColor(109,255,169), FColor(100,192,255), FColor(255,189,103)
    };
    static void ApplyOptionalPalette(UStaticMeshComponent* Part, const TCHAR* AssetPath)
    {
        if (!Part) return;
        if (UMaterialInterface* Material = LoadObject<UMaterialInterface>(nullptr, AssetPath))
            Part->SetMaterial(0, Material);
    }
    static const FVector SensorOffsets[3] = {
        FVector(17,0,13), FVector(10,10,13), FVector(10,-10,13)
    };
}
UStaticMeshComponent* ABuggyTelemetryActor::MakeMesh(
    ABuggyTelemetryActor* Owner, USceneComponent* Parent, const FName& Name, const FVector& Offset, const FVector& Scale)
{
    // Called only from the actor constructor; default subobjects serialize without asset files.
    UStaticMeshComponent* Part = Owner->CreateDefaultSubobject<UStaticMeshComponent>(Name);
    Part->SetupAttachment(Parent);
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
    if (Cube.Succeeded()) Part->SetStaticMesh(Cube.Object);
    Part->SetRelativeLocation(Offset);
    Part->SetRelativeScale3D(Scale);
    Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    return Part;
}
ABuggyTelemetryActor::ABuggyTelemetryActor()
{
    PrimaryActorTick.bCanEverTick = true;
    SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("BuggyRoot"));
    RootComponent = SceneRoot;
    Chassis = MakeMesh(this, SceneRoot, TEXT("CabbageChassis"), FVector(0,0,11), FVector(.35f,.22f,.105f));
    WheelFL = MakeMesh(this, SceneRoot, TEXT("WheelFL"), FVector(12,-14,5), FVector(.08f,.07f,.1f));
    WheelFR = MakeMesh(this, SceneRoot, TEXT("WheelFR"), FVector(12,14,5), FVector(.08f,.07f,.1f));
    WheelRL = MakeMesh(this, SceneRoot, TEXT("WheelRL"), FVector(-12,-14,5), FVector(.08f,.07f,.1f));
    WheelRR = MakeMesh(this, SceneRoot, TEXT("WheelRR"), FVector(-12,14,5), FVector(.08f,.07f,.1f));
    ToFFront = MakeMesh(this, SceneRoot, TEXT("ToFFront"), SensorOffsets[0], FVector(.045f,.07f,.04f));
    ToFLeft = MakeMesh(this, SceneRoot, TEXT("ToFLeft"), SensorOffsets[1], FVector(.045f,.07f,.04f));
    ToFRight = MakeMesh(this, SceneRoot, TEXT("ToFRight"), SensorOffsets[2], FVector(.045f,.07f,.04f));
}
void ABuggyTelemetryActor::BeginPlay()
{
    Super::BeginPlay();
    Socket = FUdpSocketBuilder(TEXT("CabbageVizReceiveOnly")).AsNonBlocking().AsReusable()
        .BoundToAddress(FIPv4Address::InternalLoopback).BoundToPort(ListenPort)
        .WithReceiveBufferSize(256 * 1024);
    if (!Socket) UE_LOG(LogTemp, Error, TEXT("SpatialLab: cannot bind UDP port %d"), ListenPort);
    ApplyOptionalPalette(Chassis, TEXT("/Game/SpatialLab/Materials/M_CabbageBody.M_CabbageBody"));
    for (UStaticMeshComponent* Wheel : {WheelFL.Get(), WheelFR.Get(), WheelRL.Get(), WheelRR.Get()})
        ApplyOptionalPalette(Wheel, TEXT("/Game/SpatialLab/Materials/M_Wheel.M_Wheel"));
    ApplyOptionalPalette(ToFFront, TEXT("/Game/SpatialLab/Materials/M_ToFFront.M_ToFFront"));
    ApplyOptionalPalette(ToFLeft, TEXT("/Game/SpatialLab/Materials/M_ToFLeft.M_ToFLeft"));
    ApplyOptionalPalette(ToFRight, TEXT("/Game/SpatialLab/Materials/M_ToFRight.M_ToFRight"));
    BuildDemoScene();
}
void ABuggyTelemetryActor::EndPlay(const EEndPlayReason::Type Reason)
{
    if (Socket)
    {
        Socket->Close();
        ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->DestroySocket(Socket);
        Socket = nullptr;
    }
    Super::EndPlay(Reason);
}
bool ABuggyTelemetryActor::IsSensorValid(int32 Index) const
{
    return Index >= 0 && Index < 3 && Readings[Index].bValid;
}
float ABuggyTelemetryActor::GetDistanceMm(int32 Index) const
{
    return Index >= 0 && Index < 3 ? Readings[Index].DistanceMm : -1.0f;
}
int32 ABuggyTelemetryActor::GetRecentPacketRateHz() const
{
    const double Now = FPlatformTime::Seconds();
    int32 Recent = 0;
    for (const double T : RecentPacketTimes) if (Now - T <= 2.0) ++Recent;
    return FMath::RoundToInt(Recent / 2.0f);
}
float ABuggyTelemetryActor::GetClosestValidRangeMm() const
{
    float Closest = -1.0f;
    for (const FSensorReading& R : Readings)
        if (R.bValid && (Closest < 0 || R.DistanceMm < Closest)) Closest = R.DistanceMm;
    return Closest;
}
float ABuggyTelemetryActor::GetMountAngle(int32 Index) const
{
    return SensorYaw(FMath::Clamp(Index, 0, 2));
}
bool ABuggyTelemetryActor::SetMountAngles(float Front, float Left, float Right)
{
    if (!FMath::IsFinite(Front) || !FMath::IsFinite(Left) || !FMath::IsFinite(Right) ||
        FMath::Abs(Front) > 180 || FMath::Abs(Left) > 180 || FMath::Abs(Right) > 180) return false;
    FrontMountYawDegrees = Front;
    LeftMountYawDegrees = Left;
    RightMountYawDegrees = Right;
    ClearObservations();
    return true;
}
FString ABuggyTelemetryActor::GetDemoScenarioName() const
{
    return DemoScenarioIndex == 0 ? TEXT("ARENA") :
        (DemoScenarioIndex == 1 ? TEXT("CORRIDOR") : TEXT("OPEN FIELD"));
}
void ABuggyTelemetryActor::CycleDemoScenario()
{
    DemoScenarioIndex = (DemoScenarioIndex + 1) % 3;
    DemoTimeSeconds = 0;
    ClearObservations();
    ApplyDemoScenario();
}
double ABuggyTelemetryActor::GetStreamAgeSeconds() const
{
    return LastPacketAt < 0.0 ? 999.0 : FMath::Max(0.0, FPlatformTime::Seconds() - LastPacketAt);
}
void ABuggyTelemetryActor::SetDemoMode(bool bEnabled)
{
    if (bDemoMode == bEnabled) return;
    bDemoMode = bEnabled;
    bPaused = false;
    bExternalPose = false;
    LastPacketAt = -1.0;
    RecentPacketTimes.Reset();
    DemoTimeSeconds = 0;
    SetActorLocation(FVector::ZeroVector);
    EstimatedYawDegrees = 0;
    PitchDegrees = 0;
    RollDegrees = 0;
    bHaveImu = false;
    ClearObservations();
    for (FSensorReading& Reading : Readings) Reading = FSensorReading();
    SetDemoGeometryVisibility();
}
bool ABuggyTelemetryActor::ExportObservationsCsv()
{
    if (Observations.Num() == 0)
    {
        LastExportStatus = TEXT("No observations to export");
        return false;
    }
    const FString Folder = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("SpatialLab"));
    IPlatformFile& FS = FPlatformFileManager::Get().GetPlatformFile();
    if (!FS.CreateDirectoryTree(*Folder))
    {
        LastExportStatus = TEXT("Could not create CSV export directory");
        return false;
    }
    const FString Name = FString::Printf(TEXT("observations_%s.csv"), *FDateTime::UtcNow().ToString(TEXT("%Y%m%d_%H%M%S")));
    const FString File = FPaths::Combine(Folder, Name);
    FString Csv = TEXT("sensor,x_m,y_m,z_m,age_s,frame_quality\n");
    const double Now = FPlatformTime::Seconds();
    static const TCHAR* Names[3] = {TEXT("front"),TEXT("left"),TEXT("right")};
    for (const FObservedPoint& P : Observations)
    {
        const TCHAR* Quality = P.bSynthetic ? TEXT("synthetic") : (P.bHasPose ? TEXT("unverified_external_pose") : TEXT("no_xy_pose"));
        Csv += FString::Printf(TEXT("%s,%.4f,%.4f,%.4f,%.3f,%s\n"),
            Names[FMath::Clamp(P.SensorIndex,0,2)], P.Position.X/100.f, P.Position.Y/100.f,
            P.Position.Z/100.f, Now-P.TimeSeconds, Quality);
    }
    const bool bOK = FFileHelper::SaveStringToFile(Csv, *File);
    LastExportStatus = bOK ? FString::Printf(TEXT("Exported %d points to Saved/SpatialLab"), Observations.Num()) : TEXT("CSV write failed");
    return bOK;
}
void ABuggyTelemetryActor::ClearObservations()
{
    Observations.Reset();
    for (double& At : LastPointAt) At = -1.0;
}
void ABuggyTelemetryActor::ToggleDemoGeometry()
{
    bShowDemoGeometry = !bShowDemoGeometry;
    SetDemoGeometryVisibility();
}
void ABuggyTelemetryActor::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
    // Consume UDP even in demo, avoiding the socket buffer flooding while simulation runs.
    ReceivePackets();
    if (!bPaused && bDemoMode) UpdateDemo(DeltaTime);
    if (!bPaused && !bDemoMode && GetStreamAgeSeconds() > 1.5)
    {
        for (FSensorReading& Sensor : Readings) Sensor.bValid = false;
        bHaveImu = false;
    }
    const double Now = FPlatformTime::Seconds();
    if (!bPaused)
    {
        Observations.RemoveAll([this, Now](const FObservedPoint& P) {
            return Now - P.TimeSeconds > PointLifetimeSeconds;
        });
    }
    DrawWorld();
}
void ABuggyTelemetryActor::ReceivePackets()
{
    if (!Socket) return;
    uint32 Pending = 0;
    for (int32 Iter = 0; Iter < 24 && Socket->HasPendingData(Pending); ++Iter)
    {
        TArray<uint8> Bytes;
        Bytes.SetNumUninitialized(FMath::Min(Pending, (uint32)4096));
        int32 Read = 0;
        if (!Socket->Recv(Bytes.GetData(), Bytes.Num(), Read) || Read <= 0) break;
        if (!bDemoMode && !bPaused)
        {
            FUTF8ToTCHAR Decoded(reinterpret_cast<const ANSICHAR*>(Bytes.GetData()), Read);
            ApplyPacket(FString(Decoded.Length(), Decoded.Get()));
        }
    }
}
void ABuggyTelemetryActor::ApplyPacket(const FString& Payload)
{
    if (Payload.Len() > 4096) { ++RejectedPacketCount; return; }
    TSharedPtr<FJsonObject> Root;
    if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Payload), Root) || !Root.IsValid())
    {
        ++RejectedPacketCount; return;
    }
    double Schema = 0;
    if (!Root->TryGetNumberField(TEXT("schema"), Schema) || Schema != 2)
    {
        ++RejectedPacketCount; return;
    }
    const TArray<TSharedPtr<FJsonValue>>* Array = nullptr;
    if (!Root->TryGetArrayField(TEXT("sensors"), Array) || Array->Num() != 3)
    {
        ++RejectedPacketCount; return;
    }
    FSensorReading Next[3];
    bool Seen[3] = {false,false,false};
    for (const TSharedPtr<FJsonValue>& Value : *Array)
    {
        if (!Value.IsValid() || Value->Type != EJson::Object) { ++RejectedPacketCount; return; }
        const TSharedPtr<FJsonObject> Sensor = Value->AsObject();
        FString Id;
        bool bValid = false;
        if (!Sensor->TryGetStringField(TEXT("id"), Id) ||
            !Sensor->TryGetBoolField(TEXT("valid"), bValid))
        { ++RejectedPacketCount; return; }
        int32 Index = Id == TEXT("front") ? 0 : (Id == TEXT("left") ? 1 : (Id == TEXT("right") ? 2 : -1));
        if (Index < 0 || Seen[Index]) { ++RejectedPacketCount; return; }
        Seen[Index] = true;
        double Millimeters = -1.0;
        if (bValid)
        {
            if (!Sensor->TryGetNumberField(TEXT("distance_mm"), Millimeters) ||
                !FMath::IsFinite(Millimeters) ||
                Millimeters < 20.0 || Millimeters > MaximumAcceptedDistanceMm)
            { ++RejectedPacketCount; return; }
        }
        Next[Index].DistanceMm = bValid ? (float)Millimeters : -1.0f;
        Next[Index].bValid = bValid;
        Next[Index].UpdatedAt = FPlatformTime::Seconds();
    }
    const TSharedPtr<FJsonObject>* Pose = nullptr;
    bool bHasPose = Root->TryGetObjectField(TEXT("pose"), Pose);
    double X = 0, Y = 0, Yaw = 0;
    if (bHasPose)
    {
        if (!(*Pose)->TryGetNumberField(TEXT("x_m"), X) ||
            !(*Pose)->TryGetNumberField(TEXT("y_m"), Y) ||
            !(*Pose)->TryGetNumberField(TEXT("yaw_deg"), Yaw) ||
            !FMath::IsFinite(X) || !FMath::IsFinite(Y) || !FMath::IsFinite(Yaw) ||
            FMath::Abs(X) > 50 || FMath::Abs(Y) > 50 || FMath::Abs(Yaw) > 36000)
        { ++RejectedPacketCount; return; }
    }
    const TSharedPtr<FJsonObject>* Imu = nullptr;
    if (Root->TryGetObjectField(TEXT("imu"), Imu))
    {
        double GX=0, GY=0, GZ=0, AX=0, AY=0, AZ=0, Dt=0;
        const bool bOK = (*Imu)->TryGetNumberField(TEXT("gyro_x_dps"), GX) &&
            (*Imu)->TryGetNumberField(TEXT("gyro_y_dps"), GY) &&
            (*Imu)->TryGetNumberField(TEXT("gyro_z_dps"), GZ) &&
            (*Imu)->TryGetNumberField(TEXT("accel_x_g"), AX) &&
            (*Imu)->TryGetNumberField(TEXT("accel_y_g"), AY) &&
            (*Imu)->TryGetNumberField(TEXT("accel_z_g"), AZ) &&
            (*Imu)->TryGetNumberField(TEXT("dt_s"), Dt) &&
            FMath::IsFinite(GX) && FMath::IsFinite(GY) && FMath::IsFinite(GZ) &&
            FMath::IsFinite(AX) && FMath::IsFinite(AY) && FMath::IsFinite(AZ) &&
            FMath::IsFinite(Dt) && Dt > 0 && Dt <= 0.2 &&
            FMath::Abs(GX) <= 2000 && FMath::Abs(GY) <= 2000 && FMath::Abs(GZ) <= 2000 &&
            FMath::Abs(AX) <= 16 && FMath::Abs(AY) <= 16 && FMath::Abs(AZ) <= 16;
        if (!bOK) { ++RejectedPacketCount; return; }
        LastGyroscopeDps = FVector((float)GX, (float)GY, (float)GZ);
        LastAccelerometerG = FVector((float)AX, (float)AY, (float)AZ);
        bHaveImu = true;
        if (!bHasPose) EstimatedYawDegrees = FMath::UnwindDegrees(EstimatedYawDegrees + (float)(GZ * Dt));
        float RollPrediction = RollDegrees + (float)(GX * Dt);
        float PitchPrediction = PitchDegrees + (float)(GY * Dt);
        const double GravityMag = FMath::Sqrt(AX*AX + AY*AY + AZ*AZ);
        if (GravityMag > .75 && GravityMag < 1.25)
        {
            const float AccRoll = FMath::RadiansToDegrees(FMath::Atan2((float)AY,(float)AZ));
            const float AccPitch = FMath::RadiansToDegrees(FMath::Atan2((float)-AX,(float)FMath::Sqrt(AY*AY+AZ*AZ)));
            RollPrediction = FMath::Lerp(RollPrediction, AccRoll, .035f);
            PitchPrediction = FMath::Lerp(PitchPrediction, AccPitch, .035f);
        }
        RollDegrees = FMath::Clamp(RollPrediction, -75.f, 75.f);
        PitchDegrees = FMath::Clamp(PitchPrediction, -75.f, 75.f);
    }
    else bHaveImu = false;
    if (bHasPose)
    {
        SetActorLocation(FVector((float)(X * 100.0), (float)(Y * 100.0), 0.0f));
        EstimatedYawDegrees = FMath::UnwindDegrees((float)Yaw);
    }
    SetActorRotation(FRotator(PitchDegrees, EstimatedYawDegrees, RollDegrees));
    bExternalPose = bHasPose;
    const double Now = FPlatformTime::Seconds();
    for (int32 i=0;i<3;++i)
    {
        Readings[i] = Next[i];
        if (Next[i].bValid) RecordObservation(i, Next[i].DistanceMm, Now);
    }
    LastPacketAt = Now;
    RecentPacketTimes.Add(Now);
    RecentPacketTimes.RemoveAll([Now](double T) { return Now - T > 2.0; });
    ++AcceptedPacketCount;
}
FVector ABuggyTelemetryActor::SensorOrigin(int32 Index) const
{
    return GetActorLocation() + GetActorRotation().RotateVector(SensorOffsets[Index]);
}
float ABuggyTelemetryActor::SensorYaw(int32 Index) const
{
    return Index == 0 ? FrontMountYawDegrees : (Index == 1 ? LeftMountYawDegrees : RightMountYawDegrees);
}
FVector ABuggyTelemetryActor::SensorDirection(int32 Index) const
{
    // Rotate the configured ToF direction by the visualized 3D attitude (tilt included).
    const float LocalHeading = FMath::DegreesToRadians(SensorYaw(Index));
    return GetActorRotation().RotateVector(FVector(FMath::Cos(LocalHeading), FMath::Sin(LocalHeading), 0)).GetSafeNormal();
}
void ABuggyTelemetryActor::RecordObservation(int32 Index, float Mm, double Now)
{
    if (LastPointAt[Index] >= 0.0 && Now - LastPointAt[Index] < 0.12) return;
    LastPointAt[Index] = Now;
    if (Observations.Num() >= FMath::Clamp(MaxObservationCount, 10, 2000))
        Observations.RemoveAt(0, Observations.Num() - FMath::Clamp(MaxObservationCount, 10, 2000) + 1);
    FObservedPoint Point;
    Point.Position = SensorOrigin(Index) + SensorDirection(Index) * (Mm / 10.0f);
    Point.SensorIndex = Index;
    Point.TimeSeconds = Now;
    Point.bSynthetic = bDemoMode;
    Point.bHasPose = bExternalPose;
    Observations.Add(Point);
}
bool ABuggyTelemetryActor::RayBoxHit2D(const FVector& Start, const FVector& Dir, const FDemoObstacle& Box, float& HitCm) const
{
    float TMin = 0.0f;
    float TMax = MaximumAcceptedDistanceMm / 10.0f;
    for (int32 k=0;k<2;++k)
    {
        const float S = k == 0 ? Start.X : Start.Y;
        const float D = k == 0 ? Dir.X : Dir.Y;
        const float C = k == 0 ? Box.Center.X : Box.Center.Y;
        const float H = k == 0 ? Box.HalfSize.X : Box.HalfSize.Y;
        if (FMath::Abs(D) < 0.0001f)
        {
            if (S < C-H || S > C+H) return false;
        }
        else
        {
            float A = (C-H-S) / D;
            float B = (C+H-S) / D;
            if (A > B) Swap(A,B);
            TMin = FMath::Max(TMin, A);
            TMax = FMath::Min(TMax, B);
            if (TMax < TMin) return false;
        }
    }
    HitCm = TMin > 0.01f ? TMin : TMax;
    return HitCm > 2.0f && HitCm <= MaximumAcceptedDistanceMm / 10.0f;
}
void ABuggyTelemetryActor::UpdateDemo(float DeltaTime)
{
    DemoTimeSeconds += FMath::Clamp(DeltaTime, 0.0f, 0.1f);
    SetActorLocation(FVector(20.0f * FMath::Sin(DemoTimeSeconds * .22f),
                             16.0f * FMath::Sin(DemoTimeSeconds * .15f), 0));
    EstimatedYawDegrees = 13.0f * FMath::Sin(DemoTimeSeconds * .28f);
    SetActorRotation(FRotator(0, EstimatedYawDegrees, 0));
    const double Now = FPlatformTime::Seconds();
    bExternalPose = true; // Known synthetic ground-truth pose, not measured.
    bHaveImu = true;
    LastAccelerometerG = FVector(0,0,1);
    LastGyroscopeDps = FVector(0,0,3.64f * FMath::Cos(DemoTimeSeconds * .28f));
    PitchDegrees = 0;
    RollDegrees = 0;
    for (int32 i=0; i<3; ++i)
    {
        const FVector Start = SensorOrigin(i);
        const FVector Dir = SensorDirection(i);
        float Best = MaximumAcceptedDistanceMm / 10.0f + 1.0f;
        for (const FDemoObstacle& Obstacle : DemoBoxes)
        {
            float Hit = 0;
            if (RayBoxHit2D(Start, Dir, Obstacle, Hit)) Best = FMath::Min(Best, Hit);
        }
        const bool Valid = Best <= MaximumAcceptedDistanceMm / 10.0f;
        Readings[i].bValid = Valid;
        Readings[i].DistanceMm = Valid ? Best * 10.0f : -1.0f;
        Readings[i].UpdatedAt = Now;
        if (Valid) RecordObservation(i, Best * 10.0f, Now);
    }
}
void ABuggyTelemetryActor::BuildDemoScene()
{
    UWorld* World = GetWorld();
    if (!World) return;
    UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
    if (!Cube) { UE_LOG(LogTemp, Warning, TEXT("SpatialLab: engine cube mesh unavailable")); return; }
    AStaticMeshActor* Floor = World->SpawnActor<AStaticMeshActor>(FVector(0,0,-9), FRotator::ZeroRotator);
    if (Floor)
    {
        Floor->GetStaticMeshComponent()->SetMobility(EComponentMobility::Movable);
        Floor->GetStaticMeshComponent()->SetStaticMesh(Cube);
        Floor->GetStaticMeshComponent()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Floor->SetActorScale3D(FVector(13,13,0.035f));
        ApplyOptionalPalette(Floor->GetStaticMeshComponent(), TEXT("/Game/SpatialLab/Materials/M_Floor.M_Floor"));
    }
    ADirectionalLight* Light = World->SpawnActor<ADirectionalLight>(FVector(0,0,500), FRotator(-52,27,0));
    if (Light) Light->GetLightComponent()->SetIntensity(5.0f);
    const FVector Centers[] = {
        FVector(180,0,50), FVector(100,150,40), FVector(105,-145,55),
        FVector(-150,60,60), FVector(-145,-160,30)
    };
    const FVector Halves[] = {
        FVector(30,42,50), FVector(30,35,40), FVector(33,35,55),
        FVector(45,30,60), FVector(24,54,30)
    };
    for (int32 i=0;i<5;++i)
    {
        FDemoObstacle Obstacle;
        Obstacle.Center = Centers[i];
        Obstacle.HalfSize = Halves[i];
        AStaticMeshActor* Shape = World->SpawnActor<AStaticMeshActor>(Centers[i], FRotator::ZeroRotator);
        if (Shape)
        {
            Shape->GetStaticMeshComponent()->SetMobility(EComponentMobility::Movable);
            Shape->GetStaticMeshComponent()->SetStaticMesh(Cube);
            Shape->GetStaticMeshComponent()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
            Shape->SetActorScale3D(Halves[i] * 0.02f);
            ApplyOptionalPalette(Shape->GetStaticMeshComponent(), TEXT("/Game/SpatialLab/Materials/M_Obstacle.M_Obstacle"));
            Obstacle.Visual = Shape;
        }
        DemoBoxes.Add(Obstacle);
    }
    ApplyDemoScenario();
}
void ABuggyTelemetryActor::ApplyDemoScenario()
{
    const FVector Arena[] = {
        FVector(180,0,50), FVector(100,150,40), FVector(105,-145,55),
        FVector(-150,60,60), FVector(-145,-160,30)
    };
    const FVector ArenaHalf[] = {
        FVector(30,42,50), FVector(30,35,40), FVector(33,35,55),
        FVector(45,30,60), FVector(24,54,30)
    };
    const FVector Corridor[] = {
        FVector(175,85,45), FVector(175,-85,45), FVector(40,125,50),
        FVector(40,-125,50), FVector(-175,0,40)
    };
    const FVector CorridorHalf[] = {
        FVector(125,15,45), FVector(125,15,45), FVector(25,60,50),
        FVector(25,60,50), FVector(25,40,40)
    };
    for (int32 i=0; i<DemoBoxes.Num() && i<5; ++i)
    {
        FDemoObstacle& B = DemoBoxes[i];
        B.Center = DemoScenarioIndex == 0 ? Arena[i] :
            (DemoScenarioIndex == 1 ? Corridor[i] : FVector(3000+i*200,0,40));
        B.HalfSize = DemoScenarioIndex == 0 ? ArenaHalf[i] :
            (DemoScenarioIndex == 1 ? CorridorHalf[i] : FVector(30,30,40));
        if (B.Visual.IsValid())
        {
            B.Visual->SetActorLocation(B.Center);
            B.Visual->SetActorScale3D(B.HalfSize*0.02f);
        }
    }
    SetDemoGeometryVisibility();
}
void ABuggyTelemetryActor::SetDemoGeometryVisibility()
{
    const bool bVisible = bDemoMode && bShowDemoGeometry;
    for (FDemoObstacle& Box : DemoBoxes)
        if (Box.Visual.IsValid()) Box.Visual->SetActorHiddenInGame(!bVisible);
}
void ABuggyTelemetryActor::DrawWorld()
{
    UWorld* World = GetWorld();
    if (!World) return;
    // Unambiguous metric grid and axes; 100 UU = 1 metre.
    for (int32 i=-6;i<=6;++i)
    {
        const float Offset = (float)i * 100;
        const FColor Grey(36,82,92);
        DrawDebugLine(World, FVector(Offset,-600,0), FVector(Offset,600,0), Grey, false, 0, 0, .6f);
        DrawDebugLine(World, FVector(-600,Offset,0), FVector(600,Offset,0), Grey, false, 0, 0, .6f);
    }
    DrawDebugLine(World, FVector(-600,0,1), FVector(600,0,1), FColor(89,152,203), false, 0, 0, 1.8f);
    DrawDebugLine(World, FVector(0,-600,1), FVector(0,600,1), FColor(66,167,132), false, 0, 0, 1.8f);
    if (bDemoMode && bShowDemoGeometry)
    {
        for (const FDemoObstacle& Box : DemoBoxes)
            DrawDebugBox(World, Box.Center, Box.HalfSize + FVector(1,1,1), FColor(126,154,188), false, 0, 0, 2);
    }
    for (const FObservedPoint& Point : Observations)
        DrawDebugPoint(World, Point.Position, 7.0f, SensorColors[Point.SensorIndex], false, 0);
    const FVector Forward = GetActorRotation().RotateVector(FVector(1,0,0));
    const FVector Above = GetActorLocation()+FVector(0,0,28);
    DrawDebugDirectionalArrow(World, Above, Above+Forward*46.f, 12.f, FColor(134,255,167), false, 0, 0, 2.5f);
    if (!bShowRays) return;
    for (int32 i=0;i<3;++i)
    {
        const FVector Start = SensorOrigin(i);
        const FVector Dir = SensorDirection(i);
        const float LengthCm = Readings[i].bValid ? Readings[i].DistanceMm / 10.0f :
            MaximumAcceptedDistanceMm / 10.0f;
        const FColor Color = Readings[i].bValid ? SensorColors[i] : FColor(108,117,123);
        const FVector End = Start + Dir * LengthCm;
        DrawDebugDirectionalArrow(World, Start, End, 10, Color, false, 0, 0, 2.1f);
        const float Spread = FMath::DegreesToRadians(12.5f);
        const float Base = FMath::DegreesToRadians(EstimatedYawDegrees + SensorYaw(i));
        for (int32 Side=-1;Side<=1;Side+=2)
        {
            const float Rad = Base + Side * Spread;
            const FVector Edge = Start + FVector(FMath::Cos(Rad),FMath::Sin(Rad),0) * LengthCm;
            DrawDebugLine(World, Start, Edge, Color, false, 0, 0, .5f);
        }
        DrawDebugSphere(World, Start, 5.0f, 8, SensorColors[i], false, 0, 0, 1.6f);
        if (Readings[i].bValid)
        {
            const FString DistLabel = FString::Printf(TEXT("%s / %.0f mm"),
                i == 0 ? TEXT("FRONT") : (i==1 ? TEXT("LEFT") : TEXT("RIGHT")),
                Readings[i].DistanceMm);
            DrawDebugString(World, End+FVector(0,0,12), DistLabel, nullptr, Color, 0, false, 1.0f);
        }
    }
}
