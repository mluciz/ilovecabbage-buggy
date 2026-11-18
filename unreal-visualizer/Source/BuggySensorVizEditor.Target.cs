using UnrealBuildTool;
using System.Collections.Generic;
public class BuggySensorVizEditorTarget : TargetRules
{
    public BuggySensorVizEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V5;
        ExtraModuleNames.Add("BuggySensorViz");
    }
}
