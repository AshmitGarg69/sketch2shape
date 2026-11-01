from sketch2shape.vision.prompt_composer import NEGATIVE, allowlisted, compose


def test_blank_prompt_uses_palette_and_no_view_on_auto():
    p = compose("chair", "", n=4)
    assert len(p.positive) == 4 and p.hedge_index == 3
    assert p.positive[0].startswith("chair, warm brown wooden frame")
    assert "view" not in p.positive[0] and p.material == "wood"
    assert p.negative == NEGATIVE


def test_user_text_passed_through_and_hedge_is_allowlist_only():
    p = compose("chair", "a fire-breathing dragon with red scales", n=3)
    assert "fire-breathing dragon" in p.positive[0]
    assert "dragon" not in p.positive[2] and "red" in p.positive[2]


def test_viewpoint_and_material_preset():
    p = compose("car", "", viewpoint="side profile", material_preset="Wood", n=2)
    assert "side profile view" in p.positive[0] and "wooden" in p.positive[0]


def test_allowlisted_dedupes():
    assert allowlisted("Blue blue METAL thing, shiny") == "blue metal"


def test_fully_allowlisted_prompt_makes_hedge_identical():
    p = compose("mug", "matte red ceramic", n=4)
    assert p.positive[3] == p.positive[0]   # so s3 must not raise the "prompt conflict" notice
