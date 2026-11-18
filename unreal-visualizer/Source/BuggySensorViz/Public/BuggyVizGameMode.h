#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "BuggyVizGameMode.generated.h"
class ABuggyTelemetryActor;
class UBuggyVizDashboard;

UCLASS()
class BUGGYSENSORVIZ_API ABuggyVizGameMode : public AGameModeBase
{
    GENERATED_BODY()
public:
    ABuggyVizGameMode();
    virtual void BeginPlay() override;
private:
    UPROPERTY(Transient) TObjectPtr<ABuggyTelemetryActor> Visualizer;
    UPROPERTY(Transient) TObjectPtr<UBuggyVizDashboard> Dashboard;
};
