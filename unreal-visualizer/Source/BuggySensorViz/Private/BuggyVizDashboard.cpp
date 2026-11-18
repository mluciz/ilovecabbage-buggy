#include "BuggyVizDashboard.h"
#include "BuggyTelemetryActor.h"
#include "BuggyVizCameraPawn.h"
#include "Blueprint/WidgetTree.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/Border.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Components/ScrollBox.h"
#include "Components/TextBlock.h"
#include "Components/Button.h"
#include "Components/Spacer.h"
#include "Components/ProgressBar.h"
#include "Components/EditableTextBox.h"
#include "Misc/DefaultValueHelper.h"
#include "GameFramework/PlayerController.h"
#include "HAL/PlatformTime.h"

namespace VizStyle
{
    static const FLinearColor Background(0.018f, 0.036f, 0.058f, 0.93f);
    static const FLinearColor Muted(0.57f, 0.70f, 0.77f, 1.0f);
    static const FLinearColor White(0.91f, 0.96f, 1.0f, 1.0f);
    static const FLinearColor Lime(0.54f, 0.99f, 0.65f, 1.0f);
    static const FLinearColor Blue(0.41f, 0.82f, 1.0f, 1.0f);
    static const FLinearColor Orange(1.0f, 0.69f, 0.38f, 1.0f);
}
void UBuggyVizDashboard::SetVisualizer(ABuggyTelemetryActor* NewVisualizer)
{
    Visualizer = NewVisualizer;
    Refresh();
}
void UBuggyVizDashboard::NativeConstruct()
{
    Super::NativeConstruct();
    if (!WidgetTree->RootWidget) BuildInterface();
    Refresh();
}
void UBuggyVizDashboard::NativeTick(const FGeometry& Geometry, float Delta)
{
    Super::NativeTick(Geometry, Delta);
    RefreshAccumulator += Delta;
    if (RefreshAccumulator >= 0.15f)
    {
        RefreshAccumulator = 0.0f;
        Refresh();
    }
}
UTextBlock* UBuggyVizDashboard::AddText(UVerticalBox* Box, const FString& Value, int32 Size, const FLinearColor& Color, float PadTop)
{
    UTextBlock* Text = WidgetTree->ConstructWidget<UTextBlock>();
    Text->SetText(FText::FromString(Value));
    Text->SetColorAndOpacity(FSlateColor(Color));
    FSlateFontInfo Font = Text->GetFont();
    Font.Size = Size;
    Text->SetFont(Font);
    Text->SetAutoWrapText(true);
    if (Box)
    {
        UVerticalBoxSlot* Slot = Box->AddChildToVerticalBox(Text);
        Slot->SetPadding(FMargin(0, PadTop, 0, 5));
    }
    return Text;
}
UButton* UBuggyVizDashboard::AddButton(UVerticalBox* Box, const FString& Value)
{
    UButton* Button = WidgetTree->ConstructWidget<UButton>();
    Button->SetBackgroundColor(FLinearColor(0.06f,0.19f,0.25f,1.0f));
    UTextBlock* Label = WidgetTree->ConstructWidget<UTextBlock>();
    Label->SetText(FText::FromString(Value));
    Label->SetColorAndOpacity(FSlateColor(VizStyle::White));
    FSlateFontInfo Font = Label->GetFont();
    Font.Size = 13;
    Label->SetFont(Font);
    Label->SetJustification(ETextJustify::Center);
    Button->AddChild(Label);
    UVerticalBoxSlot* Slot = Box->AddChildToVerticalBox(Button);
    Slot->SetPadding(FMargin(0, 3, 0, 5));
    return Button;
}
UBorder* UBuggyVizDashboard::AddCard(UCanvasPanel* Canvas, FVector2D Position, FVector2D Size, FAnchors Anchors, FVector2D Alignment)
{
    UBorder* Border = WidgetTree->ConstructWidget<UBorder>();
    Border->SetBrushColor(VizStyle::Background);
    Border->SetPadding(FMargin(18, 14, 18, 14));
    UCanvasPanelSlot* Slot = Canvas->AddChildToCanvas(Border);
    Slot->SetAnchors(Anchors);
    Slot->SetPosition(Position);
    Slot->SetSize(Size);
    Slot->SetAlignment(Alignment);
    return Border;
}
void UBuggyVizDashboard::BuildInterface()
{
    UCanvasPanel* Canvas = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass());
    WidgetTree->RootWidget = Canvas;

    UBorder* Header = AddCard(Canvas, FVector2D(22,18), FVector2D(370,78), FAnchors(0,0));
    UVerticalBox* HeaderBody = WidgetTree->ConstructWidget<UVerticalBox>();
    Header->SetContent(HeaderBody);
    AddText(HeaderBody, TEXT("CABBAGE  /  SPATIAL LAB"), 22, VizStyle::Lime);
    AddText(HeaderBody, TEXT("3D SENSING  •  THREE ToF NODES + 6-AXIS IMU"), 10, VizStyle::Muted);

    UBorder* Sidebar = AddCard(Canvas, FVector2D(22,110), FVector2D(360,575), FAnchors(0,0));
    UScrollBox* Scroll = WidgetTree->ConstructWidget<UScrollBox>();
    Sidebar->SetContent(Scroll);
    UVerticalBox* Stack = WidgetTree->ConstructWidget<UVerticalBox>();
    Scroll->AddChild(Stack);
    AddText(Stack, TEXT("LIVE TELEMETRY"), 16, VizStyle::White);
    ModeText = AddText(Stack, TEXT("SIMULATION"), 15, VizStyle::Lime, 8);
    LinkText = AddText(Stack, TEXT("No external stream"), 12, VizStyle::Muted);
    PoseText = AddText(Stack, TEXT("Pose: waiting..."), 12, VizStyle::Blue, 7);
    MapText = AddText(Stack, TEXT("Observations: 0"), 12, VizStyle::Muted);
    ImuText = AddText(Stack, TEXT("IMU: awaiting 6-axis data"), 11, VizStyle::Blue, 6);
    DiagnosticsText = AddText(Stack, TEXT("GOOD 0   REJECTED 0   0 Hz"), 11, VizStyle::Muted, 6);
    ProximityText = AddText(Stack, TEXT("PROXIMITY  /  NO VALID RANGE"), 14, VizStyle::Orange, 7);

    AddText(Stack, TEXT("VL53L0X  /  DISTANCE CHANNELS"), 14, VizStyle::White, 16);
    SensorTextFront = AddText(Stack, TEXT("FRONT   -- mm"), 14, VizStyle::Blue, 5);
    SensorTextLeft = AddText(Stack, TEXT("LEFT   -- mm"), 14, VizStyle::Blue, 5);
    SensorTextRight = AddText(Stack, TEXT("RIGHT   -- mm"), 14, VizStyle::Blue, 5);
    for (int32 i=0; i<3; ++i)
    {
        SensorBars[i] = WidgetTree->ConstructWidget<UProgressBar>();
        SensorBars[i]->SetPercent(0.f);
        SensorBars[i]->SetFillColorAndOpacity(i==0 ? VizStyle::Lime : (i==1 ? VizStyle::Blue : VizStyle::Orange));
        UVerticalBoxSlot* BarSlot = Stack->AddChildToVerticalBox(SensorBars[i]);
        BarSlot->SetPadding(FMargin(0, 0, 0, 8));
    }
    AddText(Stack, TEXT("SENSOR MOUNT / ANGLES (DEGREES)"), 13, VizStyle::White, 14);
    AddText(Stack, TEXT("Front / Left / Right relative to buggy forward. Edit from measured physical mounts. Applying clears old map points."), 11, VizStyle::Muted);
    for (int32 i=0;i<3;++i)
    {
        MountInputs[i] = WidgetTree->ConstructWidget<UEditableTextBox>();
        MountInputs[i]->SetHintText(FText::FromString(i==0 ? TEXT("Front deg") : (i==1 ? TEXT("Left deg") : TEXT("Right deg"))));
        MountInputs[i]->SetText(FText::AsNumber(i==0 ? 0 : (i==1 ? 55 : -55)));
        UVerticalBoxSlot* InputSlot = Stack->AddChildToVerticalBox(MountInputs[i]);
        InputSlot->SetPadding(FMargin(0, 2, 0, 4));
    }
    AddButton(Stack, TEXT("APPLY SENSOR MOUNT ANGLES"))->OnClicked.AddDynamic(this, &UBuggyVizDashboard::OnApplyMountAngles);
    AddButton(Stack, TEXT("RESTORE ASSUMED 0 / 55 / -55"))->OnClicked.AddDynamic(this, &UBuggyVizDashboard::OnResetMountAngles);
    CalibrationText = AddText(Stack, TEXT("Mount angles are UNVERIFIED assumptions"), 11, VizStyle::Orange);

    AddText(Stack, TEXT("WORKSPACE"), 14, VizStyle::White, 16);
    ScenarioText = AddText(Stack, TEXT("SCENARIO: ARENA"), 12, VizStyle::Blue);
    AddButton(Stack, TEXT("NEXT TEST ENVIRONMENT"))->OnClicked.AddDynamic(this, &UBuggyVizDashboard::OnCycleScenario);
    UButton* Demo = AddButton(Stack, TEXT("SWITCH TO LIVE STREAM"));
    Demo->OnClicked.AddDynamic(this, &UBuggyVizDashboard::OnToggleDemo);
    DemoButtonText = Cast<UTextBlock>(Demo->GetChildAt(0));
    UButton* Pause = AddButton(Stack, TEXT("PAUSE VISUALIZATION"));
    Pause->OnClicked.AddDynamic(this, &UBuggyVizDashboard::OnTogglePause);
    PauseButtonText = Cast<UTextBlock>(Pause->GetChildAt(0));
    AddButton(Stack, TEXT("CLEAR OBSERVATIONS"))->OnClicked.AddDynamic(this, &UBuggyVizDashboard::OnClearMap);
    UButton* ExportButton = AddButton(Stack, TEXT("EXPORT OBSERVATIONS TO CSV"));
    ExportButton->OnClicked.AddDynamic(this, &UBuggyVizDashboard::OnExportPoints);
    ExportText = AddText(Stack, TEXT("No CSV exported in this session"), 10, VizStyle::Muted);
    UButton* Rays = AddButton(Stack, TEXT("HIDE SENSOR RAYS"));
    Rays->OnClicked.AddDynamic(this, &UBuggyVizDashboard::OnToggleRays);
    RayButtonText = Cast<UTextBlock>(Rays->GetChildAt(0));
    UButton* Truth = AddButton(Stack, TEXT("HIDE DEMO GEOMETRY"));
    Truth->OnClicked.AddDynamic(this, &UBuggyVizDashboard::OnToggleTruth);
    TruthButtonText = Cast<UTextBlock>(Truth->GetChildAt(0));
    AddButton(Stack, TEXT("TOP / ORBIT CAMERA"))->OnClicked.AddDynamic(this, &UBuggyVizDashboard::OnToggleCamera);
    AddButton(Stack, TEXT("FOCUS CAMERA"))->OnClicked.AddDynamic(this, &UBuggyVizDashboard::OnFocusCamera);

    AddText(Stack, TEXT("MEASUREMENT INTEGRITY"), 14, VizStyle::White, 16);
    AddText(Stack, TEXT("Dots are distance hits only. Demo boxes are known simulated geometry; real obstacle shapes and precise world poses are NOT inferred from these sensors alone."), 11, VizStyle::Orange);

    UBorder* TopRight = AddCard(Canvas, FVector2D(-22,18), FVector2D(255,82), FAnchors(1,0), FVector2D(1,0));
    UVerticalBox* TopRightBody = WidgetTree->ConstructWidget<UVerticalBox>();
    TopRight->SetContent(TopRightBody);
    AddText(TopRightBody, TEXT("SENSOR FUSION / RESEARCH"), 13, VizStyle::Lime);
    AddText(TopRightBody, TEXT("READ-ONLY  |  NO MOTOR OUTPUT"), 12, VizStyle::White);
    AddText(TopRightBody, TEXT("UDP 127.0.0.1 : 48765"), 11, VizStyle::Muted);

    UBorder* Footer = AddCard(Canvas, FVector2D(-22,-20), FVector2D(560,60), FAnchors(1,1), FVector2D(1,1));
    UVerticalBox* FooterBody = WidgetTree->ConstructWidget<UVerticalBox>();
    Footer->SetContent(FooterBody);
    HelpText = AddText(FooterBody, TEXT("Q / E  ORBIT   R / T  TILT   WHEEL  ZOOM   V  TOP   F  FOCUS   HOME  RESET"), 12, VizStyle::White);
    AddText(FooterBody, TEXT("Visible beam = line of sight  |  Dot = measured range endpoint  |  Box = demo truth"), 10, VizStyle::Muted);
}
void UBuggyVizDashboard::Refresh()
{
    if (!Visualizer || !ModeText) return;
    const bool Demo = Visualizer->IsDemoMode();
    const bool Paused = Visualizer->IsPaused();
    ModeText->SetText(FText::FromString(Demo ? TEXT("MODE  /  SYNTHETIC DEMO") : TEXT("MODE  /  EXTERNAL UDP")));
    const double Age = Visualizer->GetStreamAgeSeconds();
    FString Link;
    if (Paused) Link = TEXT("PAUSED  |  visualization frozen");
    else if (Demo) Link = TEXT("INTERNAL SIMULATION  |  NOT HARDWARE");
    else if (Age < 2.0) Link = FString::Printf(TEXT("STREAM RECEIVING  |  %d accepted"), Visualizer->GetPacketCount());
    else Link = FString::Printf(TEXT("NO RECENT DATA  |  %.1fs since last packet"), FMath::Min(Age, 999.0));
    LinkText->SetText(FText::FromString(Link));
    DiagnosticsText->SetText(FText::FromString(FString::Printf(TEXT("PACKETS  %d ACCEPTED  /  %d REJECTED  /  %d Hz"),
        Visualizer->GetPacketCount(), Visualizer->GetRejectedPacketCount(), Visualizer->GetRecentPacketRateHz())));
    const float Nearest = Visualizer->GetClosestValidRangeMm();
    const FString Alert = Nearest < 0 ? TEXT("RANGE UNKNOWN - NOT CLEAR") :
        (Nearest < 250 ? FString::Printf(TEXT("CLOSE OBJECT  /  %.0f mm - BENCH ONLY"), Nearest) :
        (Nearest < 550 ? FString::Printf(TEXT("NEAR OBJECT  /  %.0f mm"), Nearest) :
            FString::Printf(TEXT("NEAREST VALID HIT  /  %.0f mm"), Nearest)));
    ProximityText->SetText(FText::FromString(Alert));
    ProximityText->SetColorAndOpacity(FSlateColor(Nearest < 0 || Nearest < 550 ? VizStyle::Orange : VizStyle::Lime));
    if (ScenarioText)
        ScenarioText->SetText(FText::FromString(FString::Printf(TEXT("TEST SCENE  /  %s"),
            *Visualizer->GetDemoScenarioName())));
    PoseText->SetText(FText::FromString(FString::Printf(TEXT("LOCAL X %.2f m  /  Y %.2f m  /  YAW %.1f deg"),
        Visualizer->GetActorLocation().X / 100.f, Visualizer->GetActorLocation().Y / 100.f, Visualizer->GetHeadingDegrees())));
    MapText->SetText(FText::FromString(FString::Printf(TEXT("POINTS  %d  /  MAX %d    |    %s"),
        Visualizer->GetObservationCount(), Visualizer->GetObservationLimit(),
        Demo ? TEXT("SIMULATED POSE") : (Visualizer->HasExternalPose() ? TEXT("EXTERNAL POSE") : TEXT("POSITION UNOBSERVED")))));
    if (ImuText)
    {
        const FVector G = Visualizer->GetGyroscopeDps();
        const FVector A = Visualizer->GetAccelerometerG();
        ImuText->SetText(FText::FromString(Visualizer->HasImu()
            ? FString::Printf(TEXT("MPU-6500 | P %.1f  R %.1f deg | Gyro %.1f/%.1f/%.1f dps | Acc %.2f/%.2f/%.2f g"),
                Visualizer->GetPitchDegrees(), Visualizer->GetRollDegrees(), G.X,G.Y,G.Z,A.X,A.Y,A.Z)
            : TEXT("MPU-6500 | NO VALID 6-AXIS SAMPLE")));
    }
    const TCHAR* Names[] = {TEXT("FRONT"), TEXT("LEFT "), TEXT("RIGHT")};
    UTextBlock* Widgets[] = {SensorTextFront, SensorTextLeft, SensorTextRight};
    for (int32 i=0; i<3; ++i)
    {
        if (!Widgets[i]) continue;
        const bool Valid = Visualizer->IsSensorValid(i);
        const float Mm = Visualizer->GetDistanceMm(i);
        const FString Value = Valid
            ? FString::Printf(TEXT("%s  %5.0f mm  /  %3.0f cm  OK"), Names[i], Mm, Mm / 10.0f)
            : FString::Printf(TEXT("%s  ---- mm  /  NO VALID HIT"), Names[i]);
        Widgets[i]->SetText(FText::FromString(Value));
        Widgets[i]->SetColorAndOpacity(FSlateColor(Valid ? VizStyle::Lime : VizStyle::Orange));
        if (SensorBars[i])
        {
            const float Percent = Valid ? 1.f-FMath::Clamp(Mm/2000.f,0.f,1.f) : 0.f;
            SensorBars[i]->SetPercent(Percent);
        }
    }
    if (DemoButtonText)
        DemoButtonText->SetText(FText::FromString(Demo ? TEXT("SWITCH TO LIVE STREAM") : TEXT("SWITCH TO DEMO")));
    if (PauseButtonText)
        PauseButtonText->SetText(FText::FromString(Paused ? TEXT("RESUME VISUALIZATION") : TEXT("PAUSE VISUALIZATION")));
    if (RayButtonText)
        RayButtonText->SetText(FText::FromString(Visualizer->AreRaysVisible() ? TEXT("HIDE SENSOR RAYS") : TEXT("SHOW SENSOR RAYS")));
    if (TruthButtonText)
        TruthButtonText->SetText(FText::FromString(Visualizer->IsDemoGeometryVisible() ? TEXT("HIDE DEMO GEOMETRY") : TEXT("SHOW DEMO GEOMETRY")));
    if (ExportText) ExportText->SetText(FText::FromString(Visualizer->GetExportStatus()));
}
void UBuggyVizDashboard::OnCycleScenario()
{
    if (Visualizer && Visualizer->IsDemoMode()) Visualizer->CycleDemoScenario();
    Refresh();
}
void UBuggyVizDashboard::OnApplyMountAngles()
{
    if (!Visualizer) return;
    float Values[3] = {0,0,0};
    for (int32 i=0;i<3;++i)
    {
        if (!MountInputs[i] || !FDefaultValueHelper::ParseFloat(MountInputs[i]->GetText().ToString(), Values[i]) ||
            !FMath::IsFinite(Values[i]) || FMath::Abs(Values[i])>180)
        {
            CalibrationText->SetText(FText::FromString(TEXT("INVALID ANGLE: use numbers -180 to +180")));
            return;
        }
    }
    if (Visualizer->SetMountAngles(Values[0],Values[1],Values[2]))
        CalibrationText->SetText(FText::FromString(TEXT("Mounted bearings applied; old points cleared. Verify physical orientation.")));
    else
        CalibrationText->SetText(FText::FromString(TEXT("Angle calibration failed")));
}
void UBuggyVizDashboard::OnResetMountAngles()
{
    if (!Visualizer) return;
    Visualizer->SetMountAngles(0,55,-55);
    for (int32 i=0;i<3;++i)
        if (MountInputs[i]) MountInputs[i]->SetText(FText::AsNumber(Visualizer->GetMountAngle(i)));
    CalibrationText->SetText(FText::FromString(TEXT("ASSUMED angles restored; NOT calibrated to hardware")));
}
void UBuggyVizDashboard::OnToggleDemo() { if (Visualizer) Visualizer->SetDemoMode(!Visualizer->IsDemoMode()); Refresh(); }
void UBuggyVizDashboard::OnTogglePause() { if (Visualizer) Visualizer->SetPaused(!Visualizer->IsPaused()); Refresh(); }
void UBuggyVizDashboard::OnClearMap() { if (Visualizer) Visualizer->ClearObservations(); Refresh(); }
void UBuggyVizDashboard::OnToggleRays() { if (Visualizer) Visualizer->ToggleRays(); }
void UBuggyVizDashboard::OnToggleTruth() { if (Visualizer) Visualizer->ToggleDemoGeometry(); }
void UBuggyVizDashboard::OnExportPoints() { if (Visualizer) Visualizer->ExportObservationsCsv(); Refresh(); }
void UBuggyVizDashboard::OnToggleCamera()
{
    if (APlayerController* PC = GetOwningPlayer())
        if (ABuggyVizCameraPawn* Pawn = Cast<ABuggyVizCameraPawn>(PC->GetPawn())) Pawn->ToggleCameraMode();
}
void UBuggyVizDashboard::OnFocusCamera()
{
    if (APlayerController* PC = GetOwningPlayer())
        if (ABuggyVizCameraPawn* Pawn = Cast<ABuggyVizCameraPawn>(PC->GetPawn())) Pawn->FocusBuggy();
}
