"""Dawn of the Tiberium Age APWorld options."""

from dataclasses import dataclass

from Options import FreeText, OptionDict, PerGameCommonOptions, Visibility


class LauncherSettings(OptionDict):
    """Reusable launcher settings. Archipelago generates the run from these options.

    Omitted settings use the bundled launcher defaults. The local launcher seed
    is ignored; Archipelago controls mission order, Grid, starters and rewards.
    """

    display_name = "Launcher Settings"
    default = {}


class RunManifest(FreeText):
    """Legacy launcher-exported deterministic run manifest as JSON."""

    visibility = Visibility.none
    display_name = "Run Manifest"
    default = ""


class GeneratedWorld(OptionDict):
    """Legacy world template; new player files need only launcher_settings."""

    visibility = Visibility.none
    display_name = "Generated World"
    default = {}


@dataclass
class DTAOptions(PerGameCommonOptions):
    launcher_settings: LauncherSettings
    generated_world: GeneratedWorld
    run_manifest: RunManifest
