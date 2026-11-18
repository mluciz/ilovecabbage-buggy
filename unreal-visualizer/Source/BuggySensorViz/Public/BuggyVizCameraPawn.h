#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "BuggyVizCameraPawn.generated.h"
class USpringArmComponent;
class UCameraComponent;
class USceneComponent;
class ABuggyTelemetryActor;

UCLASS()
class BUGGYSENSORVIZ_API ABuggyVizCameraPawn : public APawn
{
    GENERATED_BODY()
public:
    ABuggyVizCameraPawn();
    virtual void Tick(float DeltaSeconds) override;
    virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;
    void SetTrackingTarget(ABuggyTelemetryActor* Target);
    UFUNCTION(BlueprintCallable) void ToggleCameraMode();
    UFUNCTION(BlueprintCallable) void ResetCamera();
    UFUNCTION(BlueprintCallable) void FocusBuggy();
    bool IsTopDown() const { return bTopDown; }
private:
    void OrbitYaw(float Axis);
    void OrbitPitch(float Axis);
    void Zoom(float Axis);
    UPROPERTY(VisibleAnywhere) TObjectPtr<USceneComponent> SceneRoot;
    UPROPERTY(VisibleAnywhere) TObjectPtr<USpringArmComponent> SpringArm;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UCameraComponent> Camera;
    UPROPERTY() TObjectPtr<ABuggyTelemetryActor> TargetActor;
    float YawDegrees = 35.0f;
    float PitchDegrees = -55.0f;
    float DistanceCm = 670.0f;
    bool bTopDown = false;
};
