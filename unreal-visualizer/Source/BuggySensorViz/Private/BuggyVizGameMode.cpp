#include "BuggyVizGameMode.h"
#include "BuggyTelemetryActor.h"
#include "BuggyVizCameraPawn.h"
#include "BuggyVizDashboard.h"
#include "Blueprint/UserWidget.h"
#include "GameFramework/PlayerController.h"
#include "Engine/World.h"

ABuggyVizGameMode::ABuggyVizGameMode()
{
    DefaultPawnClass = ABuggyVizCameraPawn::StaticClass();
    PrimaryActorTick.bCanEverTick = true;
}
void ABuggyVizGameMode::BeginPlay()
{
    Super::BeginPlay();
    Visualizer = GetWorld()->SpawnActor<ABuggyTelemetryActor>(FVector::ZeroVector, FRotator::ZeroRotator);
    EnsureLocalInterface();
}
void ABuggyVizGameMode::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
    if (!Dashboard) EnsureLocalInterface();
}
void ABuggyVizGameMode::EnsureLocalInterface()
{
    if (!IsValid(Visualizer)) return;
    if (APlayerController* PC = GetWorld()->GetFirstPlayerController())
    {
        ABuggyVizCameraPawn* Camera = Cast<ABuggyVizCameraPawn>(PC->GetPawn());
        if (!Camera)
        {
            Camera = GetWorld()->SpawnActor<ABuggyVizCameraPawn>(FVector::ZeroVector, FRotator::ZeroRotator);
            if (Camera) PC->Possess(Camera);
        }
        if (Camera) Camera->SetTrackingTarget(Visualizer);
        PC->bShowMouseCursor = true;
        PC->bEnableClickEvents = true;
        FInputModeGameAndUI InputMode;
        InputMode.SetHideCursorDuringCapture(false);
        PC->SetInputMode(InputMode);
        Dashboard = CreateWidget<UBuggyVizDashboard>(PC, UBuggyVizDashboard::StaticClass());
        if (Dashboard)
        {
            Dashboard->SetVisualizer(Visualizer);
            Dashboard->AddToViewport(100);
        }
    }
}
