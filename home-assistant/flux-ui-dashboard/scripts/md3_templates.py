"""MD3 button-card templates and card-mod styles for Flux UI."""

from __future__ import annotations

GLASS_CARD_MOD = {
    "style": (
        "ha-card {\n"
        "  border-radius: 28px;\n"
        "  background: color-mix(in srgb, var(--md-sys-color-surface-container) 78%, transparent) !important;\n"
        "  backdrop-filter: blur(18px) saturate(140%);\n"
        "  -webkit-backdrop-filter: blur(18px) saturate(140%);\n"
        "  border: 1px solid color-mix(in srgb, var(--md-sys-color-outline-variant) 45%, transparent);\n"
        "  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.28);\n"
        "}\n"
    )
}

TITLE_CARD_MOD = {
    "style": (
        "ha-card {\n"
        "  background: transparent !important;\n"
        "  box-shadow: none !important;\n"
        "  border: none !important;\n"
        "  padding-left: 4px;\n"
        "  padding-bottom: 0;\n"
        "}\n"
        ".header {\n"
        "  font-weight: 600 !important;\n"
        "  letter-spacing: 0.01em;\n"
        "  color: var(--md-sys-color-on-surface) !important;\n"
        "}\n"
        ".subheader {\n"
        "  color: var(--md-sys-color-on-surface-variant) !important;\n"
        "  font-size: 13px;\n"
        "}\n"
    )
}

VIEW_CARD_MOD = {
    "style": (
        "ha-view {\n"
        "  background: center / cover no-repeat fixed url('/local/flux-ui/wallpapers/dark-purple.webp') !important;\n"
        "}\n"
        "#view {\n"
        "  background: transparent !important;\n"
        "  max-width: 920px;\n"
        "  margin: 0 auto;\n"
        "  padding-top: 8px;\n"
        "  padding-left: 8px;\n"
        "  padding-right: 8px;\n"
        "}\n"
        "@keyframes flux-door-pulse {\n"
        "  0%, 100% { box-shadow: 0 0 18px rgba(242, 184, 181, 0.45); }\n"
        "  50% { box-shadow: 0 0 28px rgba(242, 184, 181, 0.75); }\n"
        "}\n"
        "hui-view-sections {\n"
        "  padding-bottom: 88px;\n"
        "}\n"
    )
}

# 15.6" 1920×1080 landscape — panel views fill the viewport (no sections column cap).
TABLET_VIEW_CARD_MOD = {
    "style": (
        "ha-view {\n"
        "  background: center / cover no-repeat fixed url('/local/flux-ui/wallpapers/dark-purple.webp') !important;\n"
        "}\n"
        "#view {\n"
        "  background: transparent !important;\n"
        "  max-width: none !important;\n"
        "  width: 100% !important;\n"
        "  margin: 0 !important;\n"
        "  padding: 0 !important;\n"
        "  height: 100% !important;\n"
        "  overflow-x: hidden !important;\n"
        "  overflow-y: auto !important;\n"
        "  -webkit-overflow-scrolling: touch !important;\n"
        "}\n"
        "hui-panel-view,\n"
        "hui-view-panel {\n"
        "  width: 100% !important;\n"
        "  max-width: none !important;\n"
        "  min-height: 100% !important;\n"
        "  height: auto !important;\n"
        "  overflow: visible !important;\n"
        "}\n"
        "hui-panel-view > *,\n"
        "hui-view-panel > * {\n"
        "  width: 100% !important;\n"
        "  max-width: none !important;\n"
        "}\n"
        "@keyframes flux-door-pulse {\n"
        "  0%, 100% { box-shadow: 0 0 18px rgba(242, 184, 181, 0.45); }\n"
        "  50% { box-shadow: 0 0 28px rgba(242, 184, 181, 0.75); }\n"
        "}\n"
    )
}

# Overview only — lock page to one viewport; only the calendar .content-container pans.
TABLET_OVERVIEW_VIEW_CARD_MOD = {
    "style": (
        "ha-view {\n"
        "  background: center / cover no-repeat fixed url('/local/flux-ui/wallpapers/dark-purple.webp') !important;\n"
        "  height: 100dvh !important;\n"
        "  max-height: 100dvh !important;\n"
        "  overflow: hidden !important;\n"
        "  overscroll-behavior: none !important;\n"
        "  touch-action: none !important;\n"
        "}\n"
        "#view {\n"
        "  background: transparent !important;\n"
        "  max-width: none !important;\n"
        "  width: 100% !important;\n"
        "  height: 100dvh !important;\n"
        "  max-height: 100dvh !important;\n"
        "  margin: 0 !important;\n"
        "  padding: 0 !important;\n"
        "  overflow: hidden !important;\n"
        "  overscroll-behavior: none !important;\n"
        "  touch-action: none !important;\n"
        "}\n"
        "hui-panel-view,\n"
        "hui-view-panel {\n"
        "  width: 100% !important;\n"
        "  max-width: none !important;\n"
        "  height: 100dvh !important;\n"
        "  max-height: 100dvh !important;\n"
        "  overflow: hidden !important;\n"
        "  overscroll-behavior: none !important;\n"
        "  touch-action: none !important;\n"
        "}\n"
        "hui-panel-view > *,\n"
        "hui-view-panel > * {\n"
        "  width: 100% !important;\n"
        "  max-width: none !important;\n"
        "  height: 100dvh !important;\n"
        "  max-height: 100dvh !important;\n"
        "  overflow: hidden !important;\n"
        "  overscroll-behavior: none !important;\n"
        "  touch-action: none !important;\n"
        "}\n"
        "@keyframes flux-door-pulse {\n"
        "  0%, 100% { box-shadow: 0 0 18px rgba(242, 184, 181, 0.45); }\n"
        "  50% { box-shadow: 0 0 28px rgba(242, 184, 181, 0.75); }\n"
        "}\n"
        "@keyframes flux-tesla-charge-pulse {\n"
        "  0%, 100% {\n"
        "    box-shadow: 0 0 10px 2px rgba(102, 187, 106, 0.35),\n"
        "      0 0 28px 8px rgba(76, 175, 80, 0.22);\n"
        "  }\n"
        "  50% {\n"
        "    box-shadow: 0 0 22px 6px rgba(129, 199, 132, 0.85),\n"
        "      0 0 48px 14px rgba(76, 175, 80, 0.55);\n"
        "  }\n"
        "}\n"
    )
}

BUTTON_CARD_TEMPLATES: dict = {
    "flux_glass": {
        "styles": {
            "card": [
                {"border-radius": "28px"},
                {
                    "background": "color-mix(in srgb, var(--md-sys-color-surface-container) 78%, transparent)"
                },
                {"backdrop-filter": "blur(18px) saturate(140%)"},
                {"border": "1px solid color-mix(in srgb, var(--md-sys-color-outline-variant) 45%, transparent)"},
                {"box-shadow": "0 4px 24px rgba(0, 0, 0, 0.28)"},
                {"padding": "14px 16px"},
            ],
            "icon": [{"color": "var(--md-sys-color-primary)"}, {"width": "28px"}],
            "name": [
                {"font-weight": "600"},
                {"font-size": "14px"},
                {"white-space": "normal"},
                {"line-height": "1.25"},
                {"overflow": "visible"},
                {"text-overflow": "clip"},
                {"color": "var(--md-sys-color-on-surface)"},
            ],
            "label": [{"color": "var(--md-sys-color-on-surface-variant)"}, {"font-size": "12px"}],
        }
    },
    "flux_action": {
        "template": "flux_glass",
        "show_label": True,
        "styles": {
            "grid": [
                {"grid-template-areas": "'i n' 'i l'"},
                {"grid-template-columns": "48px 1fr"},
                {"grid-template-rows": "min-content min-content"},
            ],
            "img_cell": [
                {"background-color": "var(--contrast1)"},
                {"border-radius": "16px"},
                {"width": "48px"},
                {"height": "48px"},
            ],
            "icon": [{"width": "26px"}, {"color": "var(--md-sys-color-primary)"}],
            "name": [
                {"font-weight": "600"},
                {"font-size": "13px"},
                {"white-space": "normal"},
                {"line-height": "1.25"},
                {"overflow": "visible"},
                {"text-overflow": "clip"},
                {"justify-self": "start"},
                {"text-align": "left"},
            ],
            "label": [{"justify-self": "start"}, {"text-align": "left"}],
        },
    },
    "flux_overview_tab": {
        "show_icon": True,
        "show_label": True,
        "show_state": False,
        "styles": {
            "card": [
                {"border-radius": "28px"},
                {"padding": "14px 12px"},
                {"min-height": "48px"},
                {"width": "100%"},
                {"height": "100%"},
                {"background": "color-mix(in srgb, var(--md-sys-color-surface-container) 55%, transparent)"},
                {"border": "1px solid color-mix(in srgb, var(--md-sys-color-outline-variant) 35%, transparent)"},
                {"box-shadow": "none"},
            ],
            "grid": [
                {"grid-template-areas": "'i n'"},
                {"grid-template-columns": "min-content min-content"},
                {"grid-template-rows": "min-content"},
                {"justify-content": "center"},
                {"justify-items": "center"},
                {"align-items": "center"},
                {"column-gap": "8px"},
            ],
            "icon": [{"width": "20px"}, {"color": "var(--md-sys-color-on-surface-variant)"}],
            "name": [
                {"font-weight": "600"},
                {"font-size": "14px"},
                {"white-space": "nowrap"},
                {"text-align": "center"},
                {"color": "var(--md-sys-color-on-surface-variant)"},
            ],
        },
        "state": [
            {
                "operator": "template",
                "value": "[[[ return entity?.state === variables.tab_option ]]]",
                "styles": {
                    "card": [
                        {"background": "var(--md-sys-color-primary)"},
                        {"border": "1px solid var(--md-sys-color-primary)"},
                        {"box-shadow": "0 2px 12px rgba(208, 188, 255, 0.35)"},
                    ],
                    "icon": [{"color": "var(--md-sys-color-on-primary)"}],
                    "name": [{"color": "var(--md-sys-color-on-primary)"}, {"font-weight": "700"}],
                },
            },
        ],
    },
    "flux_light": {
        "template": "flux_glass",
        "show_label": True,
        "icon": "[[[ return entity.state === 'on' ? 'mdi:lightbulb-on' : 'mdi:lightbulb-outline'; ]]]",
        "state": [
            {
                "value": "on",
                "styles": {
                    "card": [
                        {"background": "rgba(255, 193, 7, 0.22)"},
                        {"border": "1px solid rgba(255, 193, 7, 0.72)"},
                        {"box-shadow": "0 0 18px rgba(255, 193, 7, 0.28), 0 4px 16px rgba(0, 0, 0, 0.22)"},
                    ],
                    "icon": [{"color": "#FFD54F"}],
                    "img_cell": [
                        {"background-color": "rgba(255, 193, 7, 0.45)"},
                        {"box-shadow": "0 0 12px rgba(255, 193, 7, 0.35)"},
                    ],
                    "name": [{"color": "#FFF8E1"}, {"font-weight": "700"}],
                    "label": [{"color": "#FFD54F"}, {"font-weight": "700"}],
                },
            },
            {
                "value": "off",
                "styles": {
                    "card": [
                        {
                            "background": (
                                "color-mix(in srgb, var(--md-sys-color-surface-container) 62%, transparent)"
                            )
                        },
                        {"border": "1px solid rgba(147, 143, 153, 0.28)"},
                        {"box-shadow": "none"},
                    ],
                    "icon": [{"color": "#6B6770"}],
                    "img_cell": [{"background-color": "rgba(60, 56, 65, 0.55)"}],
                    "name": [{"color": "var(--md-sys-color-on-surface-variant)"}, {"font-weight": "500"}],
                    "label": [{"color": "#6B6770"}, {"font-weight": "500"}],
                },
            },
        ],
        "styles": {
            "grid": [
                {"grid-template-areas": "'i n' 'i l'"},
                {"grid-template-columns": "48px 1fr"},
                {"grid-template-rows": "min-content min-content"},
            ],
            "img_cell": [
                {"background-color": "rgba(60, 56, 65, 0.55)"},
                {"border-radius": "16px"},
                {"width": "48px"},
                {"height": "48px"},
            ],
            "icon": [{"width": "24px"}, {"color": "#6B6770"}],
            "name": [
                {"font-weight": "600"},
                {"font-size": "15px"},
                {"justify-self": "start"},
                {"text-align": "left"},
            ],
            "label": [
                {"font-weight": "500"},
                {"font-size": "12px"},
                {"color": "#6B6770"},
                {"justify-self": "start"},
                {"text-align": "left"},
            ],
        },
    },
    "flux_room": {
        "template": "flux_glass",
        "show_icon": False,
        "show_name": False,
        "show_label": False,
        "styles": {
            "grid": [
                {"grid-template-areas": "'info sensors'"},
                {"grid-template-columns": "1fr 44px"},
                {"grid-template-rows": "1fr"},
                {"column-gap": "10px"},
                {"align-items": "stretch"},
                {"align-content": "stretch"},
                {"justify-content": "start"},
                {"height": "100%"},
                {"min-height": "0"},
            ],
            "custom_fields": {
                "info": [
                    {"grid-area": "info"},
                    {"justify-self": "start"},
                    {"align-self": "start"},
                    {"width": "100%"},
                    {"z-index": "2"},
                ],
                "bg": [
                    {"position": "absolute"},
                    {"bottom": "4px"},
                    {"left": "0"},
                    {"z-index": "0"},
                    {"pointer-events": "none"},
                    {"width": "96px"},
                    {"height": "96px"},
                    {"display": "flex"},
                    {"align-items": "flex-end"},
                    {"justify-content": "flex-start"},
                ],
                "sensors": [
                    {"grid-area": "sensors"},
                    {"justify-self": "center"},
                    {"align-self": "stretch"},
                    {"width": "40px"},
                    {"min-width": "40px"},
                    {"height": "100%"},
                    {"min-height": "0"},
                    {"padding-top": "0"},
                    {"padding-bottom": "0"},
                    {"z-index": "2"},
                ],
            },
            "card": [
                {"position": "relative"},
                {"overflow": "hidden"},
                {"padding": "14px 12px 14px 14px"},
                {"height": "186px"},
                {"min-height": "186px"},
                {"max-height": "186px"},
                {"box-sizing": "border-box"},
                {"display": "flex"},
                {"align-items": "stretch"},
            ],
        },
        "state": [
            {
                "operator": "template",
                "value": (
                    "[[[ return (variables.lights || []).some("
                    "e => states[e]?.state === 'on'); ]]]"
                ),
                "styles": {
                    "card": [
                        {
                            "background": (
                                "color-mix(in srgb, var(--md-sys-color-surface-container) "
                                "72%, rgba(255, 193, 7, 0.08))"
                            )
                        },
                        {"border": "1px solid rgba(255, 193, 7, 0.38)"},
                        {
                            "box-shadow": (
                                "0 0 20px rgba(255, 193, 7, 0.14), "
                                "0 4px 24px rgba(0, 0, 0, 0.28)"
                            )
                        },
                    ],
                    "custom_fields": {
                        "bg": [{"opacity": "0.28"}],
                    },
                },
            },
        ],
    },
    # Tablet mid-grid rooms — same as flux_room but fills the cell (no 186px lock).
    "flux_room_fill": {
        "template": "flux_glass",
        "show_icon": False,
        "show_name": False,
        "show_label": False,
        "styles": {
            "grid": [
                {"grid-template-areas": "'info sensors'"},
                {"grid-template-columns": "1fr 44px"},
                {"grid-template-rows": "1fr"},
                {"column-gap": "10px"},
                {"align-items": "stretch"},
                {"align-content": "stretch"},
                {"justify-content": "start"},
                {"height": "100%"},
                {"min-height": "0"},
                {"width": "100%"},
            ],
            "custom_fields": {
                "info": [
                    {"grid-area": "info"},
                    {"justify-self": "start"},
                    {"align-self": "start"},
                    {"width": "100%"},
                    {"z-index": "2"},
                ],
                "bg": [
                    {"position": "absolute"},
                    {"bottom": "4px"},
                    {"left": "0"},
                    {"z-index": "0"},
                    {"pointer-events": "none"},
                    {"width": "96px"},
                    {"height": "96px"},
                    {"display": "flex"},
                    {"align-items": "flex-end"},
                    {"justify-content": "flex-start"},
                ],
                "sensors": [
                    {"grid-area": "sensors"},
                    {"justify-self": "center"},
                    {"align-self": "stretch"},
                    {"width": "40px"},
                    {"min-width": "40px"},
                    {"height": "100%"},
                    {"min-height": "0"},
                    {"padding-top": "0"},
                    {"padding-bottom": "0"},
                    {"z-index": "2"},
                ],
            },
            "card": [
                {"position": "relative"},
                {"overflow": "hidden"},
                {"padding": "14px 12px 14px 14px"},
                {"height": "100%"},
                {"min-height": "0"},
                {"max-height": "none"},
                {"width": "100%"},
                {"box-sizing": "border-box"},
                {"display": "flex"},
                {"align-items": "stretch"},
            ],
        },
        "state": [
            {
                "operator": "template",
                "value": (
                    "[[[ return (variables.lights || []).some("
                    "e => states[e]?.state === 'on'); ]]]"
                ),
                "styles": {
                    "card": [
                        {
                            "background": (
                                "color-mix(in srgb, var(--md-sys-color-surface-container) "
                                "72%, rgba(255, 193, 7, 0.08))"
                            )
                        },
                        {"border": "1px solid rgba(255, 193, 7, 0.38)"},
                        {
                            "box-shadow": (
                                "0 0 20px rgba(255, 193, 7, 0.14), "
                                "0 4px 24px rgba(0, 0, 0, 0.28)"
                            )
                        },
                    ],
                    "custom_fields": {
                        "bg": [{"opacity": "0.28"}],
                    },
                },
            },
        ],
    },
    "flux_icon_button": {
        "template": "flux_glass",
        "show_icon": True,
        "show_name": False,
        "show_label": False,
        "styles": {
            "grid": [
                {"grid-template-areas": "'i'"},
                {"grid-template-columns": "1fr"},
                {"justify-items": "center"},
                {"align-items": "center"},
            ],
            "img_cell": [
                {"background-color": "rgba(208, 188, 255, 0.16)"},
                {"border-radius": "999px"},
                {"width": "40px"},
                {"height": "40px"},
            ],
            "icon": [{"width": "20px"}, {"color": "var(--md-sys-color-on-surface)"}],
            "card": [
                {"padding": "6px"},
                {"min-height": "52px"},
                {"max-height": "52px"},
                {"border-radius": "999px"},
                {"display": "flex"},
                {"align-items": "center"},
                {"justify-content": "center"},
            ],
        },
    },
    "flux_feature": {
        "template": "flux_glass",
        "show_icon": True,
        "show_name": True,
        "show_label": False,
        "styles": {
            "grid": [
                {"grid-template-areas": "'i' 'n'"},
                {"grid-template-columns": "1fr"},
                {"grid-template-rows": "min-content min-content"},
                {"justify-items": "center"},
                {"align-items": "center"},
                {"row-gap": "6px"},
            ],
            "img_cell": [
                {"background-color": "rgba(208, 188, 255, 0.16)"},
                {"border-radius": "14px"},
                {"width": "44px"},
                {"height": "44px"},
            ],
            "icon": [{"width": "22px"}, {"color": "var(--md-sys-color-on-surface-variant)"}],
            "name": [
                {"font-size": "11px"},
                {"font-weight": "600"},
                {"text-align": "center"},
                {"line-height": "1.25"},
                {"color": "var(--md-sys-color-on-surface)"},
                {"white-space": "normal"},
                {"overflow": "hidden"},
                {"display": "-webkit-box"},
                {"-webkit-line-clamp": "2"},
                {"-webkit-box-orient": "vertical"},
                {"max-width": "100%"},
                {"padding": "0 2px"},
            ],
            "card": [
                {"padding": "12px 6px"},
                {"min-height": "80px"},
                {"max-height": "80px"},
                {"display": "flex"},
                {"align-items": "center"},
                {"justify-content": "center"},
            ],
        },
    },
    "flux_fab_group": {
        "template": "flux_glass",
        "show_icon": True,
        "show_label": False,
        "styles": {
            "grid": [
                {"grid-template-areas": "'i n'"},
                {"grid-template-columns": "36px 1fr"},
                {"column-gap": "10px"},
                {"align-items": "center"},
            ],
            "img_cell": [
                {"background-color": "rgba(208, 188, 255, 0.22)"},
                {"border-radius": "12px"},
                {"width": "36px"},
                {"height": "36px"},
            ],
            "icon": [{"width": "20px"}, {"color": "var(--md-sys-color-primary)"}],
            "name": [
                {"font-size": "13px"},
                {"font-weight": "600"},
                {"justify-self": "start"},
                {"text-align": "left"},
                {"color": "var(--md-sys-color-on-surface)"},
            ],
            "card": [
                {"padding": "10px 12px"},
                {"margin-bottom": "8px"},
                {"border-radius": "999px"},
                {
                    "background": (
                        "color-mix(in srgb, var(--md-sys-color-surface-container) "
                        "82%, rgba(208, 188, 255, 0.12))"
                    )
                },
            ],
        },
    },
    "flux_room_status": {
        "show_icon": False,
        "show_name": False,
        "show_label": False,
        "styles": {
            "card": [
                {"background": "transparent"},
                {"box-shadow": "none"},
                {"border": "none"},
                {"padding": "0"},
            ],
        },
    },
    "flux_door": {
        "template": "flux_glass",
        "show_icon": True,
        "show_label": True,
        "styles": {
            "grid": [
                {"grid-template-areas": "'i n' 'i l'"},
                {"grid-template-columns": "52px 1fr"},
                {"grid-template-rows": "min-content min-content"},
                {"column-gap": "12px"},
                {"align-items": "center"},
            ],
            "img_cell": [
                {"background-color": "rgba(129, 199, 132, 0.22)"},
                {"border-radius": "18px"},
                {"width": "52px"},
                {"height": "52px"},
            ],
            "icon": [{"width": "28px"}, {"color": "#81C784"}],
            "name": [
                {"font-weight": "700"},
                {"font-size": "14px"},
                {"white-space": "normal"},
                {"line-height": "1.25"},
                {"overflow": "visible"},
                {"text-overflow": "clip"},
                {"justify-self": "start"},
                {"text-align": "left"},
                {"color": "var(--md-sys-color-on-surface)"},
            ],
            "label": [
                {"font-weight": "600"},
                {"font-size": "12px"},
                {"justify-self": "start"},
                {"color": "#81C784"},
            ],
            "card": [
                {"padding": "14px 16px"},
                {"min-height": "80px"},
                {
                    "background": (
                        "color-mix(in srgb, var(--md-sys-color-surface-container) 78%, "
                        "rgba(129, 199, 132, 0.1))"
                    )
                },
                {"border": "1px solid rgba(129, 199, 132, 0.35)"},
            ],
        },
    },
    "flux_greeting": {
        "show_icon": False,
        "show_label": True,
        "styles": {
            "card": [
                {"background": "transparent"},
                {"box-shadow": "none"},
                {"border": "none"},
                {"padding": "8px 4px 4px 8px"},
            ],
            "grid": [{"grid-template-areas": "'n' 'l'"}, {"grid-template-columns": "1fr"}],
            "name": [
                {"font-size": "22px"},
                {"font-weight": "700"},
                {"justify-self": "start"},
                {"color": "var(--md-sys-color-on-surface)"},
            ],
            "label": [
                {"font-size": "13px"},
                {"color": "var(--md-sys-color-on-surface-variant)"},
                {"justify-self": "start"},
            ],
        },
    },
    "flux_hero": {
        "template": "flux_glass",
        "show_icon": False,
        "show_entity_picture": True,
        "show_label": True,
        "show_state": False,
        "styles": {
            "grid": [
                {"grid-template-areas": "'i n' 'i l'"},
                {"grid-template-columns": "72px 1fr"},
                {"grid-template-rows": "min-content min-content"},
                {"column-gap": "20px"},
                {"row-gap": "4px"},
                {"align-items": "center"},
                {"justify-content": "start"},
            ],
            "img_cell": [
                {"background-color": "transparent"},
                {"border-radius": "50%"},
                {"width": "72px"},
                {"height": "72px"},
                {"min-width": "72px"},
                {"overflow": "hidden"},
                {"justify-self": "start"},
                {"align-self": "center"},
                {"margin-right": "4px"},
                {
                    "background-image": (
                        "[[[ return variables.avatar_url ? `url('${variables.avatar_url}')` : 'none' ]]]"
                    )
                },
                {"background-size": "cover"},
                {"background-position": "center top"},
                {"background-repeat": "no-repeat"},
            ],
            "icon": [{"display": "none"}],
            "entity_picture": [
                {"width": "100%"},
                {"height": "100%"},
                {"object-fit": "cover"},
                {"object-position": "center top"},
                {"border-radius": "50%"},
                {"display": "block"},
            ],
            "name": [
                {"font-size": "24px"},
                {"font-weight": "700"},
                {"justify-self": "start"},
                {"text-align": "left"},
                {"padding-left": "0"},
                {"margin-left": "0"},
            ],
            "label": [
                {"font-size": "13px"},
                {"color": "var(--md-sys-color-on-surface-variant)"},
                {"justify-self": "start"},
                {"text-align": "left"},
            ],
            "card": [{"padding": "18px 20px"}],
        },
    },
}


FLUX_LIGHT_ROW_MOD = {
    "style": (
        "ha-card {\n"
        "  border-radius: 20px;\n"
        "  backdrop-filter: blur(18px) saturate(140%);\n"
        "  -webkit-backdrop-filter: blur(18px) saturate(140%);\n"
        "  padding: 0 !important;\n"
        "  overflow: hidden;\n"
        "  box-shadow: none !important;\n"
        "}\n"
        "{% if is_state(config.entity, 'on') %}\n"
        "ha-card {\n"
        "  background: rgba(255, 193, 7, 0.12) !important;\n"
        "  border: 1px solid rgba(255, 193, 7, 0.48) !important;\n"
        "}\n"
        "{% else %}\n"
        "ha-card {\n"
        "  background: color-mix(in srgb, var(--md-sys-color-surface-container) 58%, transparent) !important;\n"
        "  border: 1px solid rgba(147, 143, 153, 0.24) !important;\n"
        "}\n"
        "{% endif %}\n"
    )
}

# Phone favourite / room / active lights — slim mushroom dimmer row (pre-tile era).
FLUX_SLIM_LIGHT_MOD = {
    "style": (
        GLASS_CARD_MOD["style"]
        + "ha-card {\n"
        "  padding: 10px 16px !important;\n"
        "  min-height: 56px !important;\n"
        "}\n"
        "mushroom-light-control {\n"
        "  align-items: center;\n"
        "  gap: 10px;\n"
        "  width: 100%;\n"
        "}\n"
        "mushroom-light-brightness-control {\n"
        "  flex: 1;\n"
        "  min-width: 0;\n"
        "}\n"
        "{% if is_state(config.entity, 'on') %}\n"
        "ha-card {\n"
        "  background: rgba(255, 193, 7, 0.16) !important;\n"
        "  border-color: rgba(255, 193, 7, 0.58) !important;\n"
        "  box-shadow: 0 0 14px rgba(255, 193, 7, 0.18) !important;\n"
        "}\n"
        "{% else %}\n"
        "ha-card {\n"
        "  background: color-mix(in srgb, var(--md-sys-color-surface-container) 58%, transparent) !important;\n"
        "  border-color: rgba(147, 143, 153, 0.28) !important;\n"
        "  box-shadow: none !important;\n"
        "}\n"
        "{% endif %}\n"
    )
}


def wrap_flux_light_card(card: dict) -> dict:
    """Apply slim MD3 dimmer chrome to a mushroom-light-card."""
    card = dict(card)
    card["card_mod"] = FLUX_SLIM_LIGHT_MOD
    return card


FLUX_MUSHROOM_SLIDER_MOD = {
    "style": (
        "ha-card {\n"
        "  background: transparent !important;\n"
        "  box-shadow: none !important;\n"
        "  border: none !important;\n"
        "  padding: 10px 14px 10px 0 !important;\n"
        "}\n"
        "mushroom-shape-icon {\n"
        "  display: none !important;\n"
        "}\n"
        ".primary,\n"
        ".secondary,\n"
        "mushroom-state-info {\n"
        "  display: none !important;\n"
        "}\n"
        "mushroom-light-brightness-control {\n"
        "  width: 100% !important;\n"
        "}\n"
        "mushroom-light-brightness-control mushroom-slider {\n"
        "  --bg-color: rgba(255, 255, 255, 0.16) !important;\n"
        "  --main-color: rgba(255, 193, 7, 0.95) !important;\n"
        "  height: 6px !important;\n"
        "  border-radius: 999px !important;\n"
        "}\n"
    )
}

FLUX_MUSHROOM_ACTIVE_MOD = {
    "style": (
        "ha-card {\n"
        "  border-radius: 20px;\n"
        "  backdrop-filter: blur(18px) saturate(140%);\n"
        "  -webkit-backdrop-filter: blur(18px) saturate(140%);\n"
        "  padding: 8px 14px !important;\n"
        "  box-shadow: none !important;\n"
        "}\n"
        "{% if is_state(config.entity, 'on') %}\n"
        "ha-card {\n"
        "  background: rgba(255, 193, 7, 0.12) !important;\n"
        "  border: 1px solid rgba(255, 193, 7, 0.48) !important;\n"
        "}\n"
        "{% else %}\n"
        "ha-card {\n"
        "  background: color-mix(in srgb, var(--md-sys-color-surface-container) 58%, transparent) !important;\n"
        "  border: 1px solid rgba(147, 143, 153, 0.24) !important;\n"
        "}\n"
        "{% endif %}\n"
    )
}

FLUX_LIGHTS_LIST_MOD = {
    "style": (
        "ha-card {\n"
        "  background: transparent !important;\n"
        "  box-shadow: none !important;\n"
        "  border: none !important;\n"
        "  padding: 0 !important;\n"
        "  margin: 0 !important;\n"
        "}\n"
        "#root {\n"
        "  display: flex !important;\n"
        "  flex-direction: column !important;\n"
        "  gap: 8px !important;\n"
        "}\n"
    )
}


def wrap_flux_light_row(card: dict, *, entity: str) -> dict:
    """mod-card wrapper so row styling can use entity state in card_mod."""
    return {
        "type": "custom:mod-card",
        "entity": entity,
        "card_mod": FLUX_LIGHT_ROW_MOD,
        "card": card,
    }


def merge_card_mod(card: dict, extra_style: str) -> dict:
    """Append card-mod CSS without discarding existing styles."""
    card = dict(card)
    existing = card.get("card_mod") or {}
    base = existing.get("style", "") if isinstance(existing, dict) else ""
    card["card_mod"] = {"style": base + extra_style}
    return card


def wrap_glass(card: dict) -> dict:
    card = dict(card)
    existing = card.get("card_mod") or {}
    base = existing.get("style", "") if isinstance(existing, dict) else ""
    card["card_mod"] = {"style": GLASS_CARD_MOD["style"] + base}
    return card


def wrap_title(card: dict) -> dict:
    card = dict(card)
    existing = card.get("card_mod") or {}
    base = existing.get("style", "") if isinstance(existing, dict) else ""
    card["card_mod"] = {"style": TITLE_CARD_MOD["style"] + base}
    return card
