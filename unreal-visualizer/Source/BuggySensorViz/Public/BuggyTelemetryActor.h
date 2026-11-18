#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BuggyTelemetryActor.generated.h"

class FSocket;
class UStaticMeshComponent;
class USceneComponent;
class AStaticMeshActor;

/** UDP visualization receiver. Never sends commands to physical motors. */
UCLASS()
class BUGGYSENSORVIZ_API ABuggyTelemetryActor : public AActor
{
    GENERATED_BODY()
public:
    ABuggyTelemetryActor();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaTime) override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Telemetry")
    int32 ListenPort = 48765;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Telemetry")
    float ObstaclePersistenceSeconds = 20.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Telemetry")
    float MaximumAcceptedDistanceMm = 2000.0f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Telemetry")
    float LastRangeMm = -1.0f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Telemetry")
    bool bLastRangeValid = false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Telemetry")
    int32 AcceptedPacketCount = 0;

private:
    void ApplyPacket(const FString& Payload, float DeltaTime);
    void AddRangeObservation(float RangeMm, float SensorYawDegrees);
    FSocket* Socket = nullptr;
    UPROPERTY()
    USceneComponent* SceneRoot;
    UPROPERTY()
    UStaticMeshComponent* BuggyMesh;
    struct FObservedBlock { TWeakObjectPtr<AStaticMeshActor> Actor; double Time; };
    TArray<FObservedBlock> Observations;
    double LastPacketAt = -1.0;
    double LastObservationAt = -1.0;
    float EstimatedYawDegrees = 0.0f;
};
