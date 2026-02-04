/* eslint-disable class-methods-use-this */
class EnphaseScheduleCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._hass = null;
    this._state = {
      selectedId: null,
      edit: this._emptySchedule("cfg"),
      add: this._emptySchedule("cfg"),
      error: "",
    };
  }

  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("Entity is required");
    }
    this._config = {
      domain: "enphase_envoy_cloud_control",
      add_service: "add_schedule",
      update_service: "update_schedule",
      delete_service: "delete_schedule",
      ...config,
    };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 4;
  }

  _emptySchedule(defaultType) {
    return {
      schedule_type: defaultType || "cfg",
      start_time: "00:00",
      end_time: "00:00",
      limit: 0,
      days: [],
    };
  }

  _daysLabel(days) {
    const names = {
      1: "Mon",
      2: "Tue",
      3: "Wed",
      4: "Thu",
      5: "Fri",
      6: "Sat",
      7: "Sun",
    };
    return days.map((day) => names[day] || day).join(" ");
  }

  _validate(schedule) {
    if (schedule.start_time === schedule.end_time) {
      return "Start time and end time must differ.";
    }
    if (!Array.isArray(schedule.days) || schedule.days.length === 0) {
      return "Select at least one day.";
    }
    const limit = Number(schedule.limit);
    if (Number.isNaN(limit) || limit < 0 || limit > 100) {
      return "Limit must be between 0 and 100.";
    }
    return "";
  }

  _serviceCall(service, data) {
    if (!this._hass) {
      return;
    }
    this._hass.callService(this._config.domain, service, data);
  }

  _onSelectSchedule(id) {
    const schedules = this._getSchedules();
    const selected = schedules.find((sched) => sched.id === id);
    if (!selected) {
      return;
    }
    this._state.selectedId = id;
    this._state.edit = {
      schedule_type: selected.type,
      start_time: selected.start,
      end_time: selected.end,
      limit: selected.limit,
      days: [...selected.days],
    };
    this._state.error = "";
    this._render();
  }

  _toggleDay(target, day) {
    const idx = target.days.indexOf(day);
    if (idx >= 0) {
      target.days.splice(idx, 1);
    } else {
      target.days.push(day);
      target.days.sort((a, b) => a - b);
    }
  }

  _handleSave() {
    const error = this._validate(this._state.edit);
    if (error) {
      this._state.error = error;
      this._render();
      return;
    }
    if (!this._state.selectedId) {
      this._state.error = "Select a schedule to update.";
      this._render();
      return;
    }
    this._state.error = "";
    this._serviceCall(this._config.update_service, {
      schedule_id: this._state.selectedId,
      schedule_type: this._state.edit.schedule_type,
      start_time: this._state.edit.start_time,
      end_time: this._state.edit.end_time,
      limit: Number(this._state.edit.limit),
      days: this._state.edit.days,
      confirm: true,
    });
  }

  _handleDelete() {
    if (!this._state.selectedId) {
      this._state.error = "Select a schedule to delete.";
      this._render();
      return;
    }
    this._state.error = "";
    this._serviceCall(this._config.delete_service, {
      schedule_id: this._state.selectedId,
      confirm: true,
    });
  }

  _handleAdd() {
    const error = this._validate(this._state.add);
    if (error) {
      this._state.error = error;
      this._render();
      return;
    }
    this._state.error = "";
    this._serviceCall(this._config.add_service, {
      schedule_type: this._state.add.schedule_type,
      start_time: this._state.add.start_time,
      end_time: this._state.add.end_time,
      limit: Number(this._state.add.limit),
      days: this._state.add.days,
    });
  }

  _getSchedules() {
    if (!this._hass || !this._config) {
      return [];
    }
    const entity = this._hass.states[this._config.entity];
    if (!entity || !entity.attributes || !Array.isArray(entity.attributes.schedules)) {
      return [];
    }
    return entity.attributes.schedules;
  }

  _render() {
    if (!this.shadowRoot || !this._config) {
      return;
    }
    const schedules = this._getSchedules();
    const edit = this._state.edit;
    const add = this._state.add;
    const error = this._state.error;

    this.shadowRoot.innerHTML = `
      <ha-card header="Enphase Schedules">
        <div class="card-content">
          <div class="section">
            <div class="section-title">Schedules</div>
            <div class="schedule-list">
              ${schedules
                .map(
                  (sched) => `
                    <button class="schedule-row ${this._state.selectedId === sched.id ? "selected" : ""}" data-id="${sched.id}">
                      <span class="type">${sched.type.toUpperCase()}</span>
                      <span class="time">${sched.start}–${sched.end}</span>
                      <span class="limit">${sched.limit}%</span>
                      <span class="days">${this._daysLabel(sched.days)}</span>
                    </button>
                  `
                )
                .join("")}
            </div>
          </div>

          <div class="section">
            <div class="section-title">Edit selected</div>
            <div class="row">
              <label>Type</label>
              <select class="edit-type">
                ${["cfg", "dtg", "rbd"]
                  .map(
                    (type) =>
                      `<option value="${type}" ${edit.schedule_type === type ? "selected" : ""}>${type.toUpperCase()}</option>`
                  )
                  .join("")}
              </select>
            </div>
            <div class="row">
              <label>Start</label>
              <input class="edit-start" type="time" value="${edit.start_time}" />
              <label>End</label>
              <input class="edit-end" type="time" value="${edit.end_time}" />
            </div>
            <div class="row">
              <label>Limit</label>
              <input class="edit-limit" type="number" min="0" max="100" value="${edit.limit}" />
            </div>
            <div class="row days">
              ${[1, 2, 3, 4, 5, 6, 7]
                .map(
                  (day) => `
                    <button class="day-chip ${edit.days.includes(day) ? "active" : ""}" data-day="${day}" data-target="edit">
                      ${this._daysLabel([day])}
                    </button>
                  `
                )
                .join("")}
            </div>
            <div class="row actions">
              <button class="primary save-btn">Save</button>
              <button class="secondary delete-btn">Delete</button>
            </div>
          </div>

          <div class="section">
            <div class="section-title">Add new schedule</div>
            <div class="row">
              <label>Type</label>
              <select class="add-type">
                ${["cfg", "dtg", "rbd"]
                  .map(
                    (type) =>
                      `<option value="${type}" ${add.schedule_type === type ? "selected" : ""}>${type.toUpperCase()}</option>`
                  )
                  .join("")}
              </select>
            </div>
            <div class="row">
              <label>Start</label>
              <input class="add-start" type="time" value="${add.start_time}" />
              <label>End</label>
              <input class="add-end" type="time" value="${add.end_time}" />
            </div>
            <div class="row">
              <label>Limit</label>
              <input class="add-limit" type="number" min="0" max="100" value="${add.limit}" />
            </div>
            <div class="row days">
              ${[1, 2, 3, 4, 5, 6, 7]
                .map(
                  (day) => `
                    <button class="day-chip ${add.days.includes(day) ? "active" : ""}" data-day="${day}" data-target="add">
                      ${this._daysLabel([day])}
                    </button>
                  `
                )
                .join("")}
            </div>
            <div class="row actions">
              <button class="primary add-btn">Add schedule</button>
            </div>
          </div>

          ${error ? `<div class="error">${error}</div>` : ""}
        </div>
      </ha-card>
      <style>
        .card-content {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }
        .section-title {
          font-weight: 600;
          margin-bottom: 8px;
        }
        .schedule-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .schedule-row {
          display: grid;
          grid-template-columns: auto auto auto 1fr;
          gap: 8px;
          padding: 8px;
          border: 1px solid var(--divider-color);
          background: var(--card-background-color);
          cursor: pointer;
          text-align: left;
        }
        .schedule-row.selected {
          border-color: var(--primary-color);
        }
        .row {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          gap: 8px;
        }
        .row label {
          min-width: 48px;
          font-size: 0.9em;
        }
        .days {
          gap: 6px;
        }
        .day-chip {
          border: 1px solid var(--divider-color);
          background: var(--card-background-color);
          padding: 4px 8px;
          cursor: pointer;
        }
        .day-chip.active {
          background: var(--primary-color);
          color: var(--text-primary-color);
          border-color: var(--primary-color);
        }
        .actions {
          gap: 12px;
        }
        button.primary {
          background: var(--primary-color);
          color: var(--text-primary-color);
          border: none;
          padding: 6px 12px;
          cursor: pointer;
        }
        button.secondary {
          background: var(--card-background-color);
          color: var(--primary-text-color);
          border: 1px solid var(--divider-color);
          padding: 6px 12px;
          cursor: pointer;
        }
        .error {
          color: var(--error-color);
          font-weight: 500;
        }
      </style>
    `;

    this.shadowRoot.querySelectorAll(".schedule-row").forEach((row) => {
      row.addEventListener("click", (event) => {
        const id = event.currentTarget.getAttribute("data-id");
        this._onSelectSchedule(id);
      });
    });
    this.shadowRoot.querySelector(".edit-type")?.addEventListener("change", (event) => {
      edit.schedule_type = event.target.value;
    });
    this.shadowRoot.querySelector(".edit-start")?.addEventListener("change", (event) => {
      edit.start_time = event.target.value;
    });
    this.shadowRoot.querySelector(".edit-end")?.addEventListener("change", (event) => {
      edit.end_time = event.target.value;
    });
    this.shadowRoot.querySelector(".edit-limit")?.addEventListener("change", (event) => {
      edit.limit = Number(event.target.value);
    });
    this.shadowRoot.querySelector(".add-type")?.addEventListener("change", (event) => {
      add.schedule_type = event.target.value;
    });
    this.shadowRoot.querySelector(".add-start")?.addEventListener("change", (event) => {
      add.start_time = event.target.value;
    });
    this.shadowRoot.querySelector(".add-end")?.addEventListener("change", (event) => {
      add.end_time = event.target.value;
    });
    this.shadowRoot.querySelector(".add-limit")?.addEventListener("change", (event) => {
      add.limit = Number(event.target.value);
    });
    this.shadowRoot.querySelectorAll(".day-chip").forEach((chip) => {
      chip.addEventListener("click", (event) => {
        const day = Number(event.currentTarget.getAttribute("data-day"));
        const target = event.currentTarget.getAttribute("data-target");
        if (target === "edit") {
          this._toggleDay(edit, day);
        } else {
          this._toggleDay(add, day);
        }
        this._render();
      });
    });
    this.shadowRoot.querySelector(".save-btn")?.addEventListener("click", () => this._handleSave());
    this.shadowRoot.querySelector(".delete-btn")?.addEventListener("click", () => this._handleDelete());
    this.shadowRoot.querySelector(".add-btn")?.addEventListener("click", () => this._handleAdd());
  }
}

customElements.define("enphase-schedule-card", EnphaseScheduleCard);
