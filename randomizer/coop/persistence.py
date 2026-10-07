"""Personal Shop profiles and runs that publish cooperative session updates."""

from randomizer.core.paths import APP_DIR, BACKUP_DIR
from randomizer.shop.persistence import COOP_SHOP_PATHS, ShopPersistencePaths, ShopRepository
from randomizer.shop.transitions import ShopTransitionError


COOP_STATE_PATH = APP_DIR / 'randomizer_coop_state.json'
LEGACY_COOP_SHOP_PATHS = ShopPersistencePaths(
    APP_DIR / 'shop_coop_profile.json', APP_DIR / 'shop_coop_run.json',
    APP_DIR / 'shop_coop_transaction.json', BACKUP_DIR / 'shop_coop',
)


class SharedShopRepository(ShopRepository):
    def __init__(self, publish, guard=lambda: None):
        # Finish old isolated transactions without letting their empty profile
        # overwrite the player's existing solo profile. Keep legacy files.
        legacy = ShopRepository(LEGACY_COOP_SHOP_PATHS)
        legacy.recover_pending_transaction()
        super().__init__(COOP_SHOP_PATHS)
        self.recover_pending_transaction()
        if not self.paths.profile.exists() and LEGACY_COOP_SHOP_PATHS.profile.is_file():
            super().save_profile(legacy.load_profile())
        self.publish = publish
        self.guard = guard

    def save_run(self, run):
        self.guard()
        super().save_run(run)
        self.publish()

    def save_profile(self, profile):
        self.guard()
        super().save_profile(profile)
        self.publish()

    def commit(self, profile, run, *args, **kwargs):
        self.guard()
        super().commit(profile, run, *args, **kwargs)
        self.publish()


class GuestShopRepository:
    """Local personal profile alongside a read-only host run."""
    def __init__(self, personal, run, publish=lambda: None, guard=lambda: None):
        self.personal, self.run = personal, run
        self.publish, self.guard = publish, guard

    def load(self):
        return self.load_profile(), self.run

    def load_profile(self):
        return self.personal.load_profile()

    def load_run(self):
        return self.run

    def commit(self, *args, **kwargs):
        raise ShopTransitionError('Only the co-op host can change the shared Shop run.')

    save_run = commit

    def save_profile(self, profile):
        self.guard()
        self.personal.save_profile(profile)
        self.publish()
