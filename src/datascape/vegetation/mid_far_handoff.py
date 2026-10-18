"""Selection contract for the next Work; does not integrate or emit motion."""
from copy import deepcopy


def recommended_selection(policy, distance, *, include_far_b=False):
    """Fail closed until the far candidate has linked ink/color implementation.

    Historical v05 geometry is available from the review CLI. It must not be
    mistaken for a completed optional integration layer or a middle solution.
    """
    if distance not in policy['primary']['distances']:
        raise ValueError('Expected middle or far source-depth role')
    if include_far_b:
        candidate = policy['far_micro_B']
        if distance not in candidate['allowed_distances']:
            raise ValueError('B is a far-only provisional candidate')
        raise NotImplementedError(
            'B requires linked ink + color passages and physical contact review in the next Work')
    return dict(distance=distance, primary_families=deepcopy(policy['primary']['families']),
                far_micro_B_enabled=False, v05_A_C_enabled=False,
                terrain_mask=policy['terrain_mask_default'], scene_integration=False)
