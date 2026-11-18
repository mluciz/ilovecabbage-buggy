using UnrealBuildTool;
public class BuggySensorViz : ModuleRules
{
    public BuggySensorViz(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "InputCore", "Json", "JsonUtilities", "Sockets", "Networking" });
    }
}
