# Enphase Envoy Cloud Control

## Lovelace dashboard example: Enphase schedule editor

Add the YAML below to a dashboard card and ensure the integration has created the
listed entities.

```yaml
type: vertical-stack
cards:
  - type: entities
    title: Enphase – Battery schedules (overview)
    entities:
      - entity: sensor.enphase_schedules_summary
      - entity: sensor.enphase_cfg_schedule
      - entity: sensor.enphase_dtg_schedule
      - entity: sensor.enphase_rbd_schedule
      - entity: button.force_cloud_refresh

  - type: entities
    title: Edit existing schedule
    entities:
      - entity: select.enphase_schedule_selected
        name: Schedule
      - entity: time.enphase_schedule_start
        name: Start
      - entity: time.enphase_schedule_end
        name: End
      - entity: number.enphase_schedule_limit
        name: Limit (%)
      - type: section
        label: Days
      - entity: switch.enphase_schedule_mon
      - entity: switch.enphase_schedule_tue
      - entity: switch.enphase_schedule_wed
      - entity: switch.enphase_schedule_thu
      - entity: switch.enphase_schedule_fri
      - entity: switch.enphase_schedule_sat
      - entity: switch.enphase_schedule_sun
      - type: section
      - entity: button.schedule_save
        name: Save changes
      - entity: button.schedule_delete
        name: Delete schedule

  - type: entities
    title: Add new schedule
    entities:
      - entity: select.enphase_new_schedule_type
        name: Type
      - entity: time.enphase_new_schedule_start
        name: Start
      - entity: time.enphase_new_schedule_end
        name: End
      - entity: number.enphase_new_schedule_limit
        name: Limit (%)
      - type: section
        label: Days
      - entity: switch.enphase_new_schedule_mon
      - entity: switch.enphase_new_schedule_tue
      - entity: switch.enphase_new_schedule_wed
      - entity: switch.enphase_new_schedule_thu
      - entity: switch.enphase_new_schedule_fri
      - entity: switch.enphase_new_schedule_sat
      - entity: switch.enphase_new_schedule_sun
      - type: section
      - entity: button.new_schedule_add
        name: Add schedule
```
