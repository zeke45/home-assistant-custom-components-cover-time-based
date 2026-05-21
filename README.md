# Cover Time Based Component

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
![version](https://img.shields.io/badge/version-2.2.0-blue)
![maintained](https://img.shields.io/badge/maintained-yes-green)
![license](https://img.shields.io/badge/license-MIT-green)

Composant Home Assistant pour gérer des volets roulants motorisés par **calcul temporel de position**.
Prend en charge les relais ON/OFF (switch), les scripts RF impulsionnels et la délégation vers un cover HA existant.

---

## ✨ Fonctionnalités

- 🎛️ **3 modes de contrôle** : switch (relais), script (RF one-shot), cover (délégation)
- ⚡ **Mode impulsion externe** : le relay gère lui-même le retour à OFF
- ⏱️ **Impulsion logicielle** configurable (auto-return après X secondes)
- 🛑 **Switch stop dédié** optionnel
- 📍 **Positionnement précis** (1-100%) par calcul temporel
- ⛔ **Stop inconditionnel** en position intermédiaire (1-99%)
- 🏷️ **Device class** configurable (shutter, blind, curtain, garage...)
- 🔌 **Template de disponibilité** (ex: gateway Zigbee en ligne)
- 💾 **Restauration de position** au redémarrage HA
- ⚠️ **Détection position incertaine** si HA redémarre pendant un déplacement
- 🖥️ **Configuration UI** complète (sans YAML obligatoire)
- 🔄 **Rechargement automatique** à chaque modification des options

---

## 📦 Installation

### Via HACS (recommandé)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=zeke45&repository=home-assistant-custom-components-cover-time-based&category=integration)

1. Cliquez sur le badge ci-dessus **ou** allez dans HACS → Intégrations → ⋮ → Dépôts personnalisés
2. Ajoutez l'URL : `https://github.com/zeke45/home-assistant-custom-components-cover-time-based`
3. Catégorie : **Intégration**
4. Installez **Cover Time Based**
5. Redémarrez Home Assistant

### Manuellement

1. Copiez `custom_components/cover_time_based/` dans `<config>/custom_components/`
2. Redémarrez Home Assistant

---

## 🖥️ Configuration via l'UI (recommandé)

[![Open your Home Assistant instance and add an integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=cover_time_based)

1. **Paramètres → Appareils et services → Ajouter une intégration** → recherchez **Cover Time Based**
2. **Étape 1** : Nom + type de contrôle
3. **Étape 2** : Entités et options

---

## 📝 Configuration YAML (legacy)

### Mode Switch (relais ON/OFF)

```yaml
cover:
  - platform: cover_time_based
    devices:
      volet_salon:
        name: Volet Salon
        control_type: switch
        open_switch_entity_id: switch.volet_open
        close_switch_entity_id: switch.volet_close
        stop_switch_entity_id: switch.volet_stop
        travelling_time_down: 27
        travelling_time_up: 31
        impulse_mode: true
        send_stop_at_end: false
        device_class: shutter
        availability_template: >-
          {% set t = states('sensor.mon_device_last_seen') %}
          {{ t not in ['unavailable','unknown',''] and
             (now() - t | as_datetime).total_seconds() < 300 }}
```

### Mode Script (RF / impulsion one-shot)

```yaml
cover:
  - platform: cover_time_based
    devices:
      volet_rf:
        name: Volet RF
        control_type: script
        open_script_entity_id: script.volet_open
        close_script_entity_id: script.volet_close
        stop_script_entity_id: script.volet_stop
        travelling_time_down: 25
        travelling_time_up: 25
        send_stop_at_end: false
```

### Mode Cover (délégation)

```yaml
cover:
  - platform: cover_time_based
    devices:
      volet_delegue:
        name: Volet Delegue
        control_type: cover
        cover_entity_id: cover.volet_existant
        travelling_time_down: 25
        travelling_time_up: 25
```

---

## ⚙️ Options disponibles

| Option | Type | Défaut | Description |
|---|---|---|---|
| `control_type` | `switch`\|`script`\|`cover` | `switch` | Mode de contrôle |
| `open_switch_entity_id` | entity | — | Switch ouverture |
| `close_switch_entity_id` | entity | — | Switch fermeture |
| `stop_switch_entity_id` | entity | `null` | Switch stop dédié (optionnel) |
| `open_script_entity_id` | entity | — | Script ouverture (mode script) |
| `close_script_entity_id` | entity | — | Script fermeture (mode script) |
| `stop_script_entity_id` | entity | `null` | Script stop (optionnel) |
| `cover_entity_id` | entity | — | Cover à déléguer (mode cover) |
| `travelling_time_down` | int | `25` | Temps de descente (secondes) |
| `travelling_time_up` | int | `25` | Temps de montée (secondes) |
| `impulse_mode` | bool | `true` | Relay gère son retour à OFF |
| `button_auto_return_time` | int | `0` | Impulsion logicielle en secondes |
| `send_stop_at_end` | bool | `false` | Stop aux fins de course 0% et 100% |
| `device_class` | string | `null` | shutter, blind, curtain, garage... |
| `availability_template` | template | `null` | Template de disponibilité |

> ℹ️ Le stop en position intermédiaire (1-99%) est **toujours envoyé** automatiquement.

---

## 🔧 Services disponibles

| Service | Description |
|---|---|
| `cover.open_cover` | Ouvre le volet |
| `cover.close_cover` | Ferme le volet |
| `cover.stop_cover` | Arrête le volet |
| `cover.set_cover_position` | Positionne le volet à X% (ex: 50%) |

---

## 📜 Crédits

Basé sur le projet original de [@davidramosweb](https://github.com/davidramosweb/home-assistant-custom-components-cover-time-based).
Améliorations inspirées de [@barmazu](https://github.com/barmazu/home-assistant-custom-components-cover-rf-time-based).
