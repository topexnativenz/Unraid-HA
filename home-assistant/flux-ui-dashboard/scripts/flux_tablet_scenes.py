"""ElementZoom tablet Presets / Scenes — category rows of scenic scene cards.

Reference: Preset page with Sunset / Mountain / Lake / Coastal image cards.
Uses button-card templates (no streamline-card required).
"""

from __future__ import annotations

from flux_navbar import URL_PREFIX, build_navbar_card
from flux_view_builders import scene_action_card, section_title
from md3_templates import TABLET_VIEW_CARD_MOD, wrap_glass, wrap_title

# Soft scenic gradients when no image path is configured (author mood rows).
PRESET_GRADIENTS = [
    "linear-gradient(145deg, #5b2c6f 0%, #e67e22 55%, #f5b041 100%)",
    "linear-gradient(145deg, #1a5276 0%, #5dade2 50%, #d5dbdb 100%)",
    "linear-gradient(145deg, #0e6655 0%, #48c9b0 45%, #f9e79f 100%)",
    "linear-gradient(145deg, #154360 0%, #5d6d7e 40%, #fadbd8 100%)",
    "linear-gradient(145deg, #4a235a 0%, #af7ac5 50%, #f5b7b1 100%)",
    "linear-gradient(145deg, #1c2833 0%, #873600 50%, #f8c471 100%)",
]


def _back_header() -> dict:
    return {
        "type": "horizontal-stack",
        "cards": [
            {
                "type": "custom:mushroom-chips-card",
                "chips": [
                    {
                        "type": "template",
                        "icon": "mdi:arrow-left",
                        "tap_action": {
                            "action": "navigate",
                            "navigation_path": f"{URL_PREFIX}/overview",
                        },
                        "card_mod": {
                            "style": (
                                "ha-card {\n"
                                "  --chip-background: color-mix(in srgb, "
                                "var(--md-sys-color-on-primary) 50%, transparent) !important;\n"
                                "  --color: var(--md-sys-color-primary) !important;\n"
                                "}\n"
                            )
                        },
                    }
                ],
            },
            wrap_title(
                {
                    "type": "custom:mushroom-title-card",
                    "title": "Preset ›",
                    "alignment": "start",
                }
            ),
        ],
    }


def _preset_card(item: dict, *, gradient: str) -> dict:
    """Scenic preset tile — image if provided, else mood gradient."""
    entity = item.get("entity")
    name = item.get("name") or (entity.split(".", 1)[-1].replace("_", " ").title() if entity else "Preset")
    image = item.get("image") or item.get("entity_picture")
    colors = item.get("colors") or ["#FFB74D", "#81C784", "#64B5F6", "#BA68C8"]

    dots = " ".join(
        f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
        f'background:{c};margin-left:3px;"></span>'
        for c in colors[:5]
    )

    card: dict = {
        "type": "custom:button-card",
        "template": "flux_glass",
        "name": name,
        "show_name": True,
        "show_label": True,
        "show_icon": not bool(image),
        "icon": item.get("icon", "mdi:palette"),
        "label": f"[[[ return `{dots}`; ]]]",
        "aspect_ratio": "5/3",
        "styles": {
            "card": [
                {"padding": "0"},
                {"overflow": "hidden"},
                {"background": image or gradient},
                {"background-size": "cover"},
                {"background-position": "center"},
                {"min-height": "120px"},
            ],
            "name": [
                {"justify-self": "start"},
                {"align-self": "end"},
                {"padding": "10px 12px 2px 12px"},
                {"font-weight": "700"},
                {"font-size": "14px"},
                {"color": "white"},
                {"text-shadow": "0 1px 4px rgba(0,0,0,0.55)"},
            ],
            "label": [
                {"justify-self": "end"},
                {"align-self": "end"},
                {"padding": "0 12px 10px 12px"},
            ],
            "icon": [
                {"color": "rgba(255,255,255,0.85)"},
                {"width": "36px"},
            ],
            "grid": [
                {"grid-template-areas": "'i' 'n' 'l'"},
                {"grid-template-rows": "1fr min-content min-content"},
            ],
        },
    }
    if image:
        card["show_entity_picture"] = True
        card["entity_picture"] = image
        card["styles"]["entity_picture"] = [
            {"width": "100%"},
            {"height": "100%"},
            {"object-fit": "cover"},
            {"position": "absolute"},
            {"top": "0"},
            {"left": "0"},
            {"opacity": "0.85"},
        ]
    if entity:
        card["entity"] = entity
        card["tap_action"] = {
            "action": "perform-action",
            "perform_action": "scene.turn_on",
            "target": {"entity_id": entity},
        }
    else:
        card["tap_action"] = {"action": "none"}
        card["styles"]["card"].append({"opacity": "0.75"})
    return card


def _default_preset_categories() -> list[dict]:
    """Mood rows matching the ElementZoom Preset screenshot when scenes.yaml is empty."""
    moods = [
        ("Sunset", ["Amber dusk", "Golden hour", "Ember", "Afterglow"]),
        ("Mountain", ["Peak mist", "Alpine", "Ridge", "Snowline"]),
        ("Lake", ["Still water", "Shore", "Reflection", "Cove"]),
        ("Coastal", ["Horizon", "Salt air", "Dune", "Harbour"]),
    ]
    out: list[dict] = []
    for cat, names in moods:
        out.append(
            {
                "name": cat,
                "presets": [{"name": n, "icon": "mdi:palette"} for n in names],
            }
        )
    return out


def build_tablet_scenes_view(cfg: dict, *, use_navbar_card: bool = True) -> dict:
    """Preset › landscape view with category rows."""
    scenes_cfg = cfg.get("scenes_config") or {}
    categories = scenes_cfg.get("preset_categories") or []
    if not categories:
        # Prefer configured HA scenes as a single Presets row, else mood stubs.
        manual = scenes_cfg.get("scenes") or []
        if manual:
            categories = [{"name": "Presets", "presets": manual}]
        else:
            categories = _default_preset_categories()

    rows: list[dict] = [_back_header()]
    gi = 0
    for category in categories:
        title = category.get("name") or "Presets"
        rows.append(wrap_title({"type": "custom:mushroom-title-card", "title": title}))
        cards = []
        for item in category.get("presets") or category.get("scenes") or []:
            cards.append(_preset_card(item, gradient=PRESET_GRADIENTS[gi % len(PRESET_GRADIENTS)]))
            gi += 1
        if cards:
            rows.append({"type": "grid", "columns": min(4, len(cards)), "square": False, "cards": cards})

    # Keep quick actions under presets (All Off / Goodnight).
    rows.append(section_title("Quick actions", "Scripts and master switches", compact=True))
    quick: list[dict] = []
    for item in cfg.get("quick_actions", {}).get("actions", []):
        card = scene_action_card(
            item["name"], item["subtitle"], item["icon"], item["service"], item["target"], columns=6
        )
        card.pop("grid_options", None)
        quick.append(card)
    if quick:
        rows.append({"type": "grid", "columns": 2, "square": False, "cards": quick})

    nav = build_navbar_card(use_navbar_card=use_navbar_card)
    rows.append(nav)

    return {
        "title": "Scenes",
        "icon": "mdi:layers",
        "path": "scenes",
        "type": "sections",
        "max_columns": 4,
        "dense_section_placement": True,
        "theme": "flux-ui-md3",
        "card_mod": TABLET_VIEW_CARD_MOD,
        "sections": [{"type": "grid", "cards": rows}],
    }


def build_tablet_active_view(cfg: dict, *, use_navbar_card: bool = True, use_auto_entities: bool = True) -> dict:
    """Security / activity — active lights + open doors (ElementZoom notifications vibe)."""
    from phase3_builders import build_active_lights_section, build_open_garage_section

    cards: list[dict] = [
        wrap_title({"type": "custom:mushroom-title-card", "title": "Active", "subtitle": "Live activity"}),
    ]
    if use_auto_entities:
        cards.extend(build_active_lights_section(cfg)["cards"])
    open_garage = build_open_garage_section(cfg)
    if open_garage:
        cards.extend(open_garage["cards"])
    cards.append(
        wrap_glass(
            {
                "type": "markdown",
                "content": (
                    "Active devices and open doors appear here. "
                    "Assign cameras in `cameras.yaml` for the overview security strip."
                ),
                "grid_options": {"columns": 12},
            }
        )
    )
    nav = build_navbar_card(use_navbar_card=use_navbar_card)
    nav["grid_options"] = {"columns": 12}
    cards.append(nav)
    return {
        "title": "Active",
        "icon": "mdi:shield-home",
        "path": "active",
        "type": "sections",
        "max_columns": 4,
        "dense_section_placement": True,
        "theme": "flux-ui-md3",
        "card_mod": TABLET_VIEW_CARD_MOD,
        "sections": [{"type": "grid", "cards": cards}],
    }
