#include "BuggyVizCameraPawn.h"
#include "BuggyTelemetryActor.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "Components/SceneComponent.h"
#include "Components/InputComponent.h"

ABuggyVizCameraPawn::ABuggyVizCameraPawn()
{
    PrimaryActorTick.bCanEverTick = true;
    SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("CameraPivot"));
    RootComponent = SceneRoot;
    SpringArm = CreateDefaultSubobject<USpringArmComponent>(TEXT("OrbitBoom"));
    SpringArm->SetupAttachment(SceneRoot);
    SpringArm->bDoCollisionTest = false;
    SpringArm->TargetArmLength = DistanceCm;
    SpringArm->SetRelativeRotation(FRotator(PitchDegrees, YawDegrees, 0));
    Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("ViewCamera"));
    Camera->SetupAttachment(SpringArm, USpringArmComponent::SocketName);
    Camera->FieldOfView = 64.0f;
    AutoPossessPlayer = EAutoReceiveInput::Player0;
}
void ABuggyVizCameraPawn::SetTrackingTarget(ABuggyTelemetryActor* Target)
{
    TargetActor = Target;
    FocusBuggy();
}
void ABuggyVizCameraPawn::FocusBuggy()
{
    if (IsValid(TargetActor)) SetActorLocation(TargetActor->GetActorLocation() + FVector(0,0,25));
}
void ABuggyVizCameraPawn::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (IsValid(TargetActor))
        SetActorLocation(FMath::VInterpTo(GetActorLocation(), TargetActor->GetActorLocation() + FVector(0,0,25), DeltaSeconds, 2.5f));
    SpringArm->TargetArmLength = FMath::FInterpTo(SpringArm->TargetArmLength, DistanceCm, DeltaSeconds, 7.0f);
    SpringArm->SetRelativeRotation(FMath::RInterpTo(SpringArm->GetRelativeRotation(), FRotator(bTopDown ? -88.f : PitchDegrees, bTopDown ? 0.f : YawDegrees, 0), DeltaSeconds, 7.0f));
}
void ABuggyVizCameraPawn::SetupPlayerInputComponent(UInputComponent* Input)
{
    Super::SetupPlayerInputComponent(Input);
    Input->BindAxis(TEXT("OrbitYaw"), this, &ABuggyVizCameraPawn::OrbitYaw);
    Input->BindAxis(TEXT("OrbitPitch"), this, &ABuggyVizCameraPawn::OrbitPitch);
    Input->BindAxis(TEXT("ZoomWheel"), this, &ABuggyVizCameraPawn::Zoom);
    Input->BindAction(TEXT("ToggleTop"), IE_Pressed, this, &ABuggyVizCameraPawn::ToggleCameraMode);
    Input->BindAction(TEXT("ResetView"), IE_Pressed, this, &ABuggyVizCameraPawn::ResetCamera);
    Input->BindAction(TEXT("FocusView"), IE_Pressed, this, &ABuggyVizCameraPawn::FocusBuggy);
}
void ABuggyVizCameraPawn::OrbitYaw(float Axis)
{
    if (FMath::Abs(Axis) > 0.01f) { bTopDown = false; YawDegrees = FMath::UnwindDegrees(YawDegrees + Axis * 70.0f * GetWorld()->GetDeltaSeconds()); }
}
void ABuggyVizCameraPawn::OrbitPitch(float Axis)
{
    if (FMath::Abs(Axis) > 0.01f) { bTopDown = false; PitchDegrees = FMath::Clamp(PitchDegrees + Axis * 50.0f * GetWorld()->GetDeltaSeconds(), -85.0f, -12.0f); }
}
void ABuggyVizCameraPawn::Zoom(float Axis)
{
    if (FMath::Abs(Axis) > 0.01f) DistanceCm = FMath::Clamp(DistanceCm - Axis * 85.0f, 180.0f, 1250.0f);
}
void ABuggyVizCameraPawn::ToggleCameraMode() { bTopDown = !bTopDown; }
void ABuggyVizCameraPawn::ResetCamera()
{
    bTopDown = false; YawDegrees = 35.0f; PitchDegrees = -55.0f; DistanceCm = 670.0f;
    FocusBuggy();
}
