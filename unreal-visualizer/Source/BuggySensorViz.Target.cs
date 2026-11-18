using UnrealBuildTool;
using System.Collections.Generic;
public class BuggySensorVizTarget : TargetRules
{
    public BuggySensorVizTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.V5;
        ExtraModuleNames.Add("BuggySensorViz");
    }
}
