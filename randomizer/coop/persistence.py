"""Reuse Shop transactions with isolated co-op files and read-only guests."""

from randomizer.core.paths import APP_DIR, BACKUP_DIR
from randomizer.shop.persistence import ShopPersistencePaths, ShopRepository
from randomizer.shop.transitions import ShopTransitionError


COOP_STATE_PATH = APP_DIR / 'randomizer_coop_state.json'
COOP_SHOP_PATHS = ShopPersistencePaths(
    APP_DIR / 'shop_coop_profile.json', APP_DIR / 'shop_coop_run.json',
    APP_DIR / 'shop_coop_transaction.json', BACKUP_DIR / 'shop_coop',
)


class SharedShopRepository(ShopRepository):
    def __init__(self, publish, guard=lambda: None):
        super().__init__(COOP_SHOP_PATHS)
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
    """A view, never a second progression or economic authority."""
    def __init__(self, profile, run):
        self.profile, self.run = profile, run

    def load(self):
        return self.profile, self.run

    def load_profile(self):
        return self.profile

    def load_run(self):
        return self.run

    def commit(self, *args, **kwargs):
        raise ShopTransitionError('Only the co-op host can change the shared Shop run.')

    save_profile = commit
    save_run = commit
