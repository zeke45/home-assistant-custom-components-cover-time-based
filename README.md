# Cover Time Based Component

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
![version](https://img.shields.io/badge/version-2.7.0-blue)
![maintained](https://img.shields.io/badge/maintained-yes-green)
![license](https://img.shields.io/badge/license-MIT-green)

Composant Home Assistant pour gérer des volets roulants motorisés par **calcul temporel de position**.
Prend en charge les relais ON/OFF (switch), les scripts RF impulsionnels et la délégation vers un cover HA existant.

---

## ✨ Fonctionnalités

- 🎛️ **4 modes de contrôle** : switch impulsion, switch maintenu, script (RF one-shot), cover (délégation)
- ⚡ **Switch impulsion** : le relay gère lui-même le retour à OFF — plus besoin de `impulse_mode` en UI
- ⏱️ **Switch maintenu** : HA gère le retour à OFF avec durée d'impulsion logicielle configurable
- 🛑 **Switch stop dédié** optionnel
- 📍 **Positionnement précis** (1-100%) par calcul temporel
- ⛔ **Stop inconditionnel** en position intermédiaire (1-99%)
- 🏷️ **Device class** configurable (shutter, blind, curtain, garage...)
- 🔌 **Template de disponibilité** (ex: gateway Zigbee en ligne) avec gestion robuste des erreurs
- 💾 **Restauration de position** au redémarrage HA
- ⚠️ **Détection position incertaine** si HA redémarre pendant un déplacement
- 🖥️ **Configuration UI** complète (sans YAML obligatoire)
- 🔄 **Rechargement automatique** à chaque modification des options
- ⏳ **Délai de commande** configurable (ms) pour échelonner les commandes simultanées
- 🔀 **Changement de type de contrôle** possible depuis les options UI (sans recréer l'intégration)
- 🪟 **Position ajourée** pour volets à lames fixes : service `cover_time_based.set_ajoure` + attribut `ajoure_position` calculé automatiquement
- 🔁 **Détection des actions physiques** (mode switch) : si le relai est actionné directement (bouton mural, télécommande), HA suit automatiquement la position sans intervention
- 🔄 **Détection bypass en mode cover** : si le cover délégué est déplacé depuis son app native, HA suit la position automatiquement
- 🔀 **Support tilt** pour stores vénitiens/orientables : `tilt_time_open` / `tilt_time_close` + services `open_cover_tilt`, `close_cover_tilt`, `set_cover_tilt_position`
- 🔧 **Service `set_known_position`** : force la position interne sans bouger le volet (resynchronisation après désync RF ou redémarrage HA)
- 📦 **Migration automatique YAML → UI** : au démarrage, chaque appareil YAML est proposé en entrée de configuration UI (idempotent)

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
2. **Étape 1** : Nom + type de contrôle (`switch`, `script` ou `cover`)
3. **Étape 2** : Entités et options (temps de parcours, délai, classe d'appareil, template de disponibilité…)

### Modifier une intégration existante

Depuis **Paramètres → Appareils et services → Cover Time Based → Configurer** :

1. **Étape 1** : Choisissez le type de contrôle (peut être changé à la volée)
2. **Étape 2** : Mettez à jour les entités et options

---

## 📝 Configuration YAML (legacy)

> 💡 **Migration automatique vers l'UI** : au démarrage de HA, chaque appareil déclaré en YAML est automatiquement migré en entrée de configuration UI (via `SOURCE_IMPORT`). La migration est **idempotente** — elle s'arrête si l'entrée existe déjà. Une fois la migration confirmée dans **Paramètres → Appareils et services**, vous pouvez retirer le bloc YAML de `configuration.yaml`.



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

### Commandes simultanées — échelonnage avec `command_delay`

Lorsque plusieurs volets sont actionnés en même temps (ex: scène "Tout ouvrir"), le bus radio (Zigbee, Z-Wave, RF...) peut être saturé et ignorer certaines commandes. L'option `command_delay` permet de décaler le départ de chaque volet, **sans affecter le calcul de position** (le TravelCalculator démarre exactement quand la commande physique est envoyée).

```yaml
cover:
  - platform: cover_time_based
    devices:
      volet_salon:
        name: Volet Salon
        command_delay: 0       # démarre immédiatement
        travelling_time_down: 25
        travelling_time_up: 25
      volet_cuisine:
        name: Volet Cuisine
        command_delay: 300     # démarre 300 ms après
        travelling_time_down: 25
        travelling_time_up: 25
      volet_chambre1:
        name: Volet Chambre 1
        command_delay: 600     # démarre 600 ms après
        travelling_time_down: 25
        travelling_time_up: 25
      volet_chambre2:
        name: Volet Chambre 2
        command_delay: 900     # démarre 900 ms après
        travelling_time_down: 25
        travelling_time_up: 25
      volet_bureau:
        name: Volet Bureau
        command_delay: 1200    # démarre 1,2 s après
        travelling_time_down: 25
        travelling_time_up: 25
```

> ℹ️ Le délai s'applique aux commandes **open**, **close**, **stop** et **set_position**.  
> La valeur est en **millisecondes** (0 à 10 000). Par défaut : `0` (comportement inchangé).  
> Ce paramètre est également disponible dans l'UI (options de l'intégration).

---

## ⚙️ Options disponibles

| Option | Type | Défaut | Description |
|---|---|---|---|
| `control_type` | `switch_impulse`\|`switch_sustained`\|`script`\|`cover` | `switch_impulse` | Mode de contrôle |
| `open_switch_entity_id` | entity | — | Switch ouverture |
| `close_switch_entity_id` | entity | — | Switch fermeture |
| `stop_switch_entity_id` | entity | `null` | Switch stop dédié (optionnel) |
| `open_script_entity_id` | entity | — | Script ouverture (mode script) |
| `close_script_entity_id` | entity | — | Script fermeture (mode script) |
| `stop_script_entity_id` | entity | `null` | Script stop (optionnel) |
| `cover_entity_id` | entity | — | Cover à déléguer (mode cover) |
| `travelling_time_down` | int | `25` | Temps de descente (secondes) |
| `travelling_time_up` | int | `25` | Temps de montée (secondes) |
| `switch_sustained_time` | int | `0` | Durée d'activation en secondes (mode `switch_sustained`, 0 = toute la durée) |
| `send_stop_at_end` | bool | `false` | Stop aux fins de course 0% et 100% |
| `device_class` | string | `null` | shutter, blind, curtain, garage... |
| `availability_template` | template | `null` | Template de disponibilité |
| `command_delay` | int | `0` | Délai avant envoi de commande (ms, 0–10000) |
| `slat_compression_time_down` | int | `0` | Durée compression lames en bas de course descente (secondes). Active la position ajourée. |
| `slat_compression_time_up` | int | `0` | Durée décompression lames en bas de course montée (secondes). Souvent ≥ `slat_compression_time_down`. |

> ℹ️ **YAML uniquement :** `control_type: switch` + `impulse_mode: true/false` + `button_auto_return_time` restent supportés pour la rétrocompatibilité (`button_auto_return_time` est automatiquement migré vers `switch_sustained_time` au premier démarrage).  
> En UI, utilisez directement `switch_impulse` ou `switch_sustained` — `impulse_mode` n'apparaît plus.

| `tilt_time_open` | int | `0` | Temps d'ouverture des lames orientables 0→100% (secondes). `0` = fonctionnalité désactivée. |
| `tilt_time_close` | int | `0` | Temps de fermeture des lames orientables 100→0% (secondes). `0` = fonctionnalité désactivée. |
> ℹ️ Le stop en position intermédiaire (1-99%) est **toujours envoyé** automatiquement.

---

## 🔁 Détection des actions physiques (bypass switch)

En mode **switch** (impulsion ou maintenu), le composant surveille l'état des relais d'ouverture et de fermeture. Si vous actionnez directement le relai sans passer par HA (bouton mural, télécommande RF, test physique), HA détecte le changement et **suit la position automatiquement**.

| Événement physique | Mode impulsion | Mode maintenu |
|---|---|---|
| Relai fermeture → ON | Suivi descente démarré ↓ | Suivi descente démarré ↓ |
| Relai ouverture → ON | Suivi montée démarré ↑ | Suivi montée démarré ↑ |
| Relai → OFF | Ignoré (impulsion brève) | Position figée (moteur arrêté) |

> ℹ️ **Modes script et cover** : En mode **cover** (délégation), le composant surveille désormais les changements d'état du cover délégué. Si celui-ci démarre une ouverture ou fermeture en dehors de HA, la position est suivie automatiquement. En mode **script**, la détection automatique n'est pas possible car ces modes ne disposent pas d'état "moteur en marche" observable dans HA.

---

## 🔧 Services disponibles

| Service | Description |
|---|---|
| `cover.open_cover` | Ouvre le volet |
| `cover.close_cover` | Ferme le volet |
| `cover.stop_cover` | Arrête le volet |
| `cover.set_cover_position` | Positionne le volet à X% (ex: 50%) |
| `cover_time_based.set_known_position` | Force la position interne sans bouger le volet (resynchronisation). Champ : `position` (0-100%). |
| `cover_time_based.set_ajoure` | Déplace le volet en position ajourée (lame au sol, lumière passe). Requiert `slat_compression_time_down > 0`. |

---

## 🪟 Volets à lames fixes ajourées

Certains volets à tablier possèdent des lames fixes qui permettent deux états en bas de course :

- **Ajouré** : la dernière lame repose au sol, les lames ne sont pas compressées → la lumière passe encore
- **Fermé** : le moteur continue quelques secondes, les lames se chevauchent et bloquent la lumière

### Principe du calcul de position

Le composant exclut automatiquement les phases de lames du calcul de position afin que **50% signifie vraiment 50%** de déplacement physique du tablier :

| Direction | Phase lames | Moment | Durée exclue du calcul |
|---|---|---|---|
| ⬇️ Descente | Compression | **Fin** de course | `slat_compression_time_down` |
| ⬆️ Montée | Décompression | **Début** de course | `slat_compression_time_up` |

> **Exemple** : `travelling_time_down = 25s`, `slat_compression_time_down = 3s`  
> → Temps effectif = 22s  
> → `set_cover_position(50%)` = 11s de déplacement réel → **50% physique exact** ✓  
> _(sans correction : 12,5s → 9,5s réel → 43% physique)_

### Configuration

```yaml
cover:
  - platform: cover_time_based
    devices:
      volet_salon:
        name: Volet Salon
        travelling_time_down: 25   # temps TOTAL (inclut la compression des lames)
        travelling_time_up: 26     # temps TOTAL (inclut la décompression des lames)
        slat_compression_time_down: 3   # 3s de compression en fin de descente
        slat_compression_time_up: 4     # 4s de décompression en début de montée
```

### Calibration

Pour trouver les bonnes valeurs :

1. **`slat_compression_time_down`** : fermez complètement (`close_cover`), puis ouvrez légèrement (`set_cover_position: 1`). Mesurez le temps entre le moment où la dernière lame touche le sol et l'arrêt du moteur.
2. **`slat_compression_time_up`** : depuis état fermé, déclenchez l'ouverture et mesurez le temps avant que le tablier commence à remonter physiquement.

### Résultat

Avec `slat_compression_time_down = 3s` et `travelling_time_down = 25s` :
- Temps effectif descente = 22s
- `ajoure_position = 0` (la position TravelCalculator 0% = ajouré physique)
- `set_cover_position(50%)` → 11s de déplacement réel → 50% exact ✓
- `close_cover` → descend jusqu'à ajouré (22s) puis compresse les lames (3s) → `is_fully_closed = true`

### Utilisation

**Via le service :**
```yaml
service: cover_time_based.set_ajoure
target:
  entity_id: cover.volet_salon
```

**Via une automatisation avec l'attribut :**
```yaml
service: cover.set_cover_position
target:
  entity_id: cover.volet_salon
data:
  position: "{{ state_attr('cover.volet_salon', 'ajoure_position') }}"
```

**Via un bouton dans le dashboard :**
```yaml
type: button
name: Ajouré
tap_action:
  action: perform-action
  perform_action: cover_time_based.set_ajoure
  target:
    entity_id: cover.volet_salon
```

> ℹ️ Si `slat_compression_time_down` est à `0` (défaut), la fonctionnalité est désactivée et le service `set_ajoure` logguera un avertissement.

> ⚠️ **Comportement après un stop en cours de phase lames** : si un `stop_cover` est envoyé pendant la phase de compression (`slat_phase_running = true`), la fermeture est interrompue et `is_fully_closed` reste `false`. La prochaine commande `close_cover` reprend proprement depuis le début : elle réinitialise l'état interne et relance la séquence complète (descente + compression).

---

## 🗂️ Architecture du code

| Fichier | Rôle |
|---|---|
| `const.py` | Toutes les constantes partagées (source unique de vérité) |
| `travel_calculator.py` | Calcul temporel de position (`TravelCalculator`) — sans dépendance HA |
| `cover.py` | Entité `CoverTimeBased` — logique HA |
| `config_flow.py` | Flux de configuration et d'options UI |
| `__init__.py` | Setup, unload, migration de version |
| `tests/` | Tests unitaires pytest (`TravelCalculator` + validation config flow) |

---

## 📊 Attributs d'état

En plus des attributs standard HA (`current_position`, `is_opening`, etc.), l'entité expose les attributs suivants :

### Attributs principaux

| Attribut | Type | Description |
|---|---|---|
| `current_position` | int | Position actuelle (0–100%) |
| `is_fully_closed` | bool | `true` si le volet est entièrement fermé (lames compressées) |
| `ajoure_position` | int | Position HA correspondant à l'état ajouré (calculé automatiquement) |

### Attributs de diagnostic / calibration

| Attribut | Type | Description |
|---|---|---|
| `pure_travel_time_down` | int | Temps de déplacement effectif en descente (hors phase lames), en secondes |
| `pure_travel_time_up` | int | Temps de déplacement effectif en montée (hors phase lames), en secondes |
| `slat_phase_running` | bool | `true` si la phase de compression/décompression des lames est en cours |
| `going_to_fully_closed` | bool | `true` si une commande de fermeture totale (lames comprises) est en cours |
| `tc_position` | int | Position interne du `TravelCalculator` (0–100, avant correction ajourée) |
| `tc_is_traveling` | bool | `true` si le `TravelCalculator` considère le volet en déplacement |
| `tc_direction` | str | Direction interne : `"up"`, `"down"` ou `None` |

### Attributs d'audit d'actions physiques

| Attribut | Type | Description |
|---|---|---|
| `last_physical_action` | str | Dernière action physique détectée : `"open"`, `"close"` ou `"stop"` |
| `last_physical_action_at` | str | Horodatage ISO de la dernière action physique (ex: `2024-01-15T14:32:05.123456+00:00`) |

> ℹ️ Les attributs `last_physical_action` / `last_physical_action_at` ne sont renseignés qu'en mode **switch** (impulsion ou maintenu), lorsque le relai est actionné directement sans passer par HA.

---

## ✅ Tests unitaires

Le projet inclut une suite de tests pytest exécutable sans installation de Home Assistant :

```bash
pip install -r requirements-test.txt
pytest
```

| Fichier de test | Couverture |
|---|---|
| `tests/test_travel_calculator.py` | ~30 tests — logique de position, direction, fin de course |
| `tests/test_config_flow_validation.py` | ~13 tests — validation des temps (`_validate_timing`) |

---

## 🗒️ Changelog

### v2.7.0 — Corrections critiques phase lames & migration YAML

#### 🐛 Bugs corrigés

**1 — Stop intempestif 1-2s après relance d'un `close_cover` (volet à lames)**

Quand une fermeture précédente avait été interrompue par un `stop_cover`, le flag interne `_slat_phase_cancelled` restait à `True`. À la prochaine commande `close_cover`, la phase de compression des lames était silencieusement annulée, `_is_fully_closed` n'était jamais mis à `True`, et le volet était affiché comme **ouvert à 0%** dans HA.

De plus, si `slat_compression_time_down > 0` et que la position interne était déjà à 0%, `start_travel_down()` rendait `position_reached()` immédiatement vrai, déclenchant un STOP moteur quasiment instantané après la commande CLOSE.

> **Correction :** Reset de `_slat_phase_cancelled`, `_slat_phase_running` et `_auto_stop_running` en début de `async_close_cover`, `async_open_cover` et `_async_set_position`. Si le TravelCalculator est déjà à 0%, la phase lames est exécutée directement dans `async_close_cover` sans passer par l'auto-updater.

---

**2 — État transitoire "ouvert" affiché pendant la phase de compression des lames**

Symptôme constaté dans les logs HA :
```
00:00:22 → Volet Salon a été ouvert   ← bug !
00:00:22 → Volet Salon se ferme
00:00:25 → Volet Salon a été fermé
```

Quand `position_reached()` passait à `True`, `is_traveling()` redevenait `False`. Pendant le court laps de temps avant que `auto_stop_if_necessary` marque `_slat_phase_running = True`, HA publiait un état incohérent : `is_closing = False`, `is_closed = False`, `position = 0%` → interprété comme **"ouvert"**.

> **Correction :** `_slat_phase_running = True` est maintenant positionné **synchroniquement** dans `auto_updater_hook` avant `async_schedule_update_ha_state()`, éliminant l'état transitoire.

---

**3 — Race condition : plusieurs tâches `auto_stop_if_necessary` simultanées**

`auto_stop_if_necessary` était créé comme nouvelle tâche asyncio toutes les 100 ms sans vérifier si une tâche précédente était encore en cours (pendant le `asyncio.sleep` de la phase lames). Plusieurs tâches pouvaient exécuter la phase concurremment, envoyer des commandes STOP en double ou corrompre les flags `_is_fully_closed` / `_going_to_fully_closed`.

> **Correction :** Ajout d'un flag guard `_auto_stop_running`. Une seule tâche `auto_stop_if_necessary` à la fois. Le flag est libéré dans un bloc `try/finally`.

---

**4 — Migration YAML → UI : `TypeError: Type is not JSON serializable: Template`**

Le validateur voluptuous `cv.template` convertit les valeurs de templates YAML en objets `Template`. Ces objets étaient stockés tels quels dans les options du config entry, rendant la persistance HA impossible (`json_bytes` ne sait pas sérialiser un objet `Template`). Cela provoquait également un `TypeError: Expected template to be a string` au prochain démarrage.

> **Correction :** Conversion des objets `Template` en string brute (`v.template`) dans `async_setup_platform` avant stockage. Protection défensive dans `async_setup_entry` pour les entrées existantes corrompues.

---

### v2.6.3 et antérieures

Voir l'historique des commits sur [GitHub](https://github.com/zeke45/home-assistant-custom-components-cover-time-based/commits/main).

---

## 📜 Crédits

Basé sur le projet original de [@davidramosweb](https://github.com/davidramosweb/home-assistant-custom-components-cover-time-based).
Améliorations inspirées de [@barmazu](https://github.com/barmazu/home-assistant-custom-components-cover-rf-time-based).
