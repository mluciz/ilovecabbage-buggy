#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BuggyTelemetryActor.generated.h"

class FSocket;
class USceneComponent;
class UStaticMeshComponent;
class AStaticMeshActor;

UCLASS()
class BUGGYSENSORVIZ_API ABuggyTelemetryActor : public AActor
{
    GENERATED_BODY()
public:
    ABuggyTelemetryActor();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaTime) override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

    /** Receive-only endpoint, deliberately loopback-bound. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Telemetry") int32 ListenPort = 48765;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Mapping") float PointLifetimeSeconds = 50.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Mapping") int32 MaxObservationCount = 450;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Range") float MaximumAcceptedDistanceMm = 2000.0f;
    /** Verify these three directions on the actual buggy before enabling real-world interpretation. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Mounting") float FrontMountYawDegrees = 0.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Mounting") float LeftMountYawDegrees = 55.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Mounting") float RightMountYawDegrees = -55.0f;

    bool IsDemoMode() const { return bDemoMode; }
    bool IsPaused() const { return bPaused; }
    bool IsSensorValid(int32 Index) const;
    float GetDistanceMm(int32 Index) const;
    float GetHeadingDegrees() const { return EstimatedYawDegrees; }
    float GetPitchDegrees() const { return PitchDegrees; }
    float GetRollDegrees() const { return RollDegrees; }
    FVector GetAccelerometerG() const { return LastAccelerometerG; }
    FVector GetGyroscopeDps() const { return LastGyroscopeDps; }
    bool HasImu() const { return bHaveImu; }
    int32 GetObservationCount() const { return Observations.Num(); }
    int32 GetObservationLimit() const { return MaxObservationCount; }
    int32 GetPacketCount() const { return AcceptedPacketCount; }
    int32 GetRejectedPacketCount() const { return RejectedPacketCount; }
    bool HasExternalPose() const { return bExternalPose; }
    double GetStreamAgeSeconds() const;
    void SetDemoMode(bool bEnabled);
    void SetPaused(bool bEnabled) { bPaused = bEnabled; }
    void ClearObservations();
    void ToggleRays() { bShowRays = !bShowRays; }
    void ToggleDemoGeometry();

private:
    struct FSensorReading
    {
        float DistanceMm = -1.0f;
        bool bValid = false;
        double UpdatedAt = -1.0;
    };
    struct FObservedPoint
    {
        FVector Position = FVector::ZeroVector;
        int32 SensorIndex = 0;
        double TimeSeconds = 0.0;
    };
    struct FDemoObstacle
    {
        FVector Center = FVector::ZeroVector;
        FVector HalfSize = FVector::ZeroVector;
        TWeakObjectPtr<AStaticMeshActor> Visual;
    };
    void ReceivePackets();
    void ApplyPacket(const FString& Payload);
    void UpdateDemo(float DeltaTime);
    void DrawWorld();
    void BuildDemoScene();
    void SetDemoGeometryVisibility();
    void RecordObservation(int32 SensorIndex, float DistanceMm, double Now);
    FVector SensorOrigin(int32 SensorIndex) const;
    FVector SensorDirection(int32 SensorIndex) const;
    float SensorYaw(int32 SensorIndex) const;
    bool RayBoxHit2D(const FVector& Start, const FVector& Ray, const FDemoObstacle& Box, float& HitCm) const;
    static UStaticMeshComponent* MakeMesh(ABuggyTelemetryActor* Owner, USceneComponent* Parent, const FName& Name,
                                          const FVector& Offset, const FVector& Scale);

    UPROPERTY(VisibleAnywhere) TObjectPtr<USceneComponent> SceneRoot;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> Chassis;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> WheelFL;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> WheelFR;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> WheelRL;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> WheelRR;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> ToFFront;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> ToFLeft;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> ToFRight;

    FSocket* Socket = nullptr;
    FSensorReading Readings[3];
    TArray<FObservedPoint> Observations;
    TArray<FDemoObstacle> DemoBoxes;
    double LastPacketAt = -1.0;
    double LastPointAt[3] = {-1.0,-1.0,-1.0};
    float EstimatedYawDegrees = 0.0f;
    float PitchDegrees = 0.0f;
    float RollDegrees = 0.0f;
    FVector LastAccelerometerG = FVector::ZeroVector;
    FVector LastGyroscopeDps = FVector::ZeroVector;
    bool bHaveImu = false;
    float DemoTimeSeconds = 0.0f;
    int32 AcceptedPacketCount = 0;
    int32 RejectedPacketCount = 0;
    bool bDemoMode = true;
    bool bPaused = false;
    bool bShowRays = true;
    bool bShowDemoGeometry = true;
    bool bExternalPose = false;
};
