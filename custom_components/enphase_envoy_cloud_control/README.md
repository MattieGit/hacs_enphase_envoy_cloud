# Enphase Envoy Cloud Control

## Optional: Enphase Schedule Card

This integration ships an optional custom Lovelace card for editing schedules using the
integration services. The card reads schedules from
`sensor.enphase_schedules_summary.attributes.schedules` and calls these services:

- `enphase_envoy_cloud_control.add_schedule`
- `enphase_envoy_cloud_control.update_schedule`
- `enphase_envoy_cloud_control.delete_schedule`

### Installation

1. Copy the card file into your Home Assistant `www/` folder:
   - From: `custom_components/enphase_envoy_cloud_control/www/enphase-schedule-card.js`
   - To: `/config/www/enphase-schedule-card.js`
2. Register the card as a Lovelace resource:
   - **Settings → Dashboards → Resources → Add Resource**
   - URL: `/local/enphase-schedule-card.js`
   - Type: **JavaScript Module**

### Card YAML example

```yaml
type: custom:enphase-schedule-card
entity: sensor.enphase_schedules_summary
domain: enphase_envoy_cloud_control
add_service: add_schedule
update_service: update_schedule
delete_service: delete_schedule
```

### Requirements

- The integration is installed and configured.
- The `sensor.enphase_schedules_summary` entity exists.
- The `add_schedule`, `update_schedule`, and `delete_schedule` services are registered.

## Example: Stock entities (no custom card)

You can also use the editor entities directly:

```yaml
type: entities
title: Enphase Schedule Editor
entities:
  - entity: select.enphase_schedule_selected
  - entity: select.enphase_new_schedule_type
  - entity: time.enphase_schedule_start
  - entity: time.enphase_schedule_end
  - entity: number.enphase_schedule_limit
  - entity: time.enphase_new_schedule_start
  - entity: time.enphase_new_schedule_end
  - entity: number.enphase_new_schedule_limit
  - entity: switch.enphase_schedule_mon
  - entity: switch.enphase_schedule_tue
  - entity: switch.enphase_schedule_wed
  - entity: switch.enphase_schedule_thu
  - entity: switch.enphase_schedule_fri
  - entity: switch.enphase_schedule_sat
  - entity: switch.enphase_schedule_sun
  - entity: switch.enphase_new_schedule_mon
  - entity: switch.enphase_new_schedule_tue
  - entity: switch.enphase_new_schedule_wed
  - entity: switch.enphase_new_schedule_thu
  - entity: switch.enphase_new_schedule_fri
  - entity: switch.enphase_new_schedule_sat
  - entity: switch.enphase_new_schedule_sun
  - entity: button.enphase_schedule_save
  - entity: button.enphase_schedule_delete
  - entity: button.enphase_new_schedule_add
```
