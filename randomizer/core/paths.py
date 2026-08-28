"""Shared filesystem paths for the DTA randomizer launcher."""
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, 'frozen', False))
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = PROJECT_ROOT
DTA_PUZZLE_PATH = SOURCE_DIR / 'DTA Puzzle.png'

# A one-file build is placed directly in the DTA folder. PyInstaller
# expands bundled modules to a temporary directory, so __file__ cannot locate
# the game or persistent state in frozen builds.
if FROZEN:
    GAME_ROOT = Path(sys.executable).resolve().parent
    APP_DIR = GAME_ROOT / 'RandomizerLauncherData'
else:
    APP_DIR = SOURCE_DIR
    GAME_ROOT = SOURCE_DIR.parent
WINDOW_ICON_PATH = SOURCE_DIR / 'launcher_icon.ico'
GAME_LAUNCHER_EXE = GAME_ROOT / 'LaunchVinifera.dat'
GAME_EXE = GAME_ROOT / 'game.exe'
SPAWN_INI = GAME_ROOT / 'spawn.ini'
SPAWN_MAP_INI = GAME_ROOT / 'spawnmap.ini'
OPTIONS_INI = GAME_ROOT / 'Settings' / 'ClientSettings.ini'
YR_OPTIONS_INI = GAME_ROOT / 'SUN.INI'
DEBUG_LOG = GAME_ROOT / 'Debug'
RULESMO_INI = GAME_ROOT / 'INI' / 'Rules.ini'
DISABLED_RULESMO_INI = GAME_ROOT / 'INI' / 'Rules.ini.randomizer-disabled'
BATTLE_CLIENT_INI = GAME_ROOT / 'INI' / 'Battle.ini'
STATE_PATH = APP_DIR / 'randomizer_state.json'
SHOP_PROFILE_PATH = APP_DIR / 'shop_profile.json'
SHOP_RUN_PATH = APP_DIR / 'shop_run.json'
SHOP_TRANSACTION_PATH = APP_DIR / 'shop_transaction.json'
BACKUP_DIR = APP_DIR / 'backups'
EXTRACTED_MAP_DIR = APP_DIR / 'extracted_maps'
GENERATED_MAP_DIR = APP_DIR / 'generated_maps'
CAMEO_CACHE_DIR = APP_DIR / 'cameo_cache'
CONFIG_DIR = APP_DIR / 'configs' / 'player'
LEGACY_CONFIG_DIR = APP_DIR / 'config'
LOG_DIR = APP_DIR / 'logs'
LAUNCHER_LOG = LOG_DIR / 'launcher.log'
MAP_RENDERER_DIR = GAME_ROOT / 'Resources'
