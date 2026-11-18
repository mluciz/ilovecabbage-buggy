#pragma once
#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "Components/CanvasPanelSlot.h"
#include "BuggyVizDashboard.generated.h"
class ABuggyTelemetryActor;
class UVerticalBox;
class UTextBlock;
class UButton;
class UBorder;

UCLASS()
class BUGGYSENSORVIZ_API UBuggyVizDashboard : public UUserWidget
{
    GENERATED_BODY()
public:
    void SetVisualizer(ABuggyTelemetryActor* NewVisualizer);
protected:
    virtual void NativeConstruct() override;
    virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;
private:
    void BuildInterface();
    void Refresh();
    UTextBlock* AddText(UVerticalBox* Box, const FString& Value, int32 Size, const FLinearColor& Color, float PadTop = 0.0f);
    UButton* AddButton(UVerticalBox* Box, const FString& Value);
    UBorder* AddCard(class UCanvasPanel* Canvas, FVector2D Position, FVector2D Size, FAnchors Anchors, FVector2D Alignment = FVector2D::ZeroVector);
    UFUNCTION() void OnToggleDemo();
    UFUNCTION() void OnTogglePause();
    UFUNCTION() void OnClearMap();
    UFUNCTION() void OnToggleRays();
    UFUNCTION() void OnToggleTruth();
    UFUNCTION() void OnExportPoints();
    UFUNCTION() void OnToggleCamera();
    UFUNCTION() void OnFocusCamera();
    UPROPERTY() TObjectPtr<ABuggyTelemetryActor> Visualizer;
    UPROPERTY() TObjectPtr<UTextBlock> ModeText;
    UPROPERTY() TObjectPtr<UTextBlock> LinkText;
    UPROPERTY() TObjectPtr<UTextBlock> PoseText;
    UPROPERTY() TObjectPtr<UTextBlock> MapText;
    UPROPERTY() TObjectPtr<UTextBlock> ImuText;
    UPROPERTY() TObjectPtr<UTextBlock> HelpText;
    UPROPERTY() TObjectPtr<UTextBlock> SensorTextFront;
    UPROPERTY() TObjectPtr<UTextBlock> SensorTextLeft;
    UPROPERTY() TObjectPtr<UTextBlock> SensorTextRight;
    UPROPERTY() TObjectPtr<UTextBlock> ExportText;
    UPROPERTY() TObjectPtr<UTextBlock> RayButtonText;
    UPROPERTY() TObjectPtr<UTextBlock> TruthButtonText;
    UPROPERTY() TObjectPtr<UTextBlock> DemoButtonText;
    UPROPERTY() TObjectPtr<UTextBlock> PauseButtonText;
    float RefreshAccumulator = 0.0f;
};
