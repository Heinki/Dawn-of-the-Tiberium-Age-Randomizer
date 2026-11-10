"""Shared challenge rules and durable application receipts for personal Shops."""


def challenges_enabled(run):
    return bool(run and run.reward_settings.get('coop_mode')
                and run.reward_settings.get('coop_challenges_version') == 1)


def receipt_key(run, mission_code):
    return f'{run.stage}:{run.emergency_revivals_used}:{mission_code}'


def challenge_receipt(run, mission_code):
    if not challenges_enabled(run):
        return None
    return run.coop_challenge_receipts.get(receipt_key(run, mission_code))


def applied_enemy_buff_count(run, mission_code):
    """Pay for applied stacks only; an unprepared mission has no receipt."""
    receipt = challenge_receipt(run, mission_code)
    return len(receipt['enemy_reward_ids']) if receipt is not None else 0
