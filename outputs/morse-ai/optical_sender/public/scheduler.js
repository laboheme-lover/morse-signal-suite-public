import {deepFreeze, id} from './protocol.js';
export const PAGE_VERSION = 'optical-sender-1.0.0';

// All timestamps describe JavaScript processing, never physical light emission.
export class Sender {
  constructor({now = () => performance.now(), requestFrame = cb => requestAnimationFrame(cb),
    cancelFrame = handle => cancelAnimationFrame(handle), paint, notify = () => {},
    checkEnvironment = () => null, wallClock = () => new Date().toISOString()}) {
    Object.assign(this, {now, requestFrame, cancelFrame, paint, notify, checkEnvironment, wallClock});
    this.active = false; this.log = null; this.handle = null;
  }
  start(plan, device = {}) {
    if (this.active) throw new Error('すでに送信中です。');
    this.plan = deepFreeze(JSON.parse(JSON.stringify(plan)));
    this.origin = this.now(); this.signalOrigin = this.origin + plan.timing.pre_start_wait_ms;
    this.next = 0; this.active = true;
    this.log = {schema_version: '1.0.0', record_type: 'run', run_id: id('run'), plan_id: plan.plan_id,
      page_version: PAGE_VERSION, device, started_at: this.wallClock(), ended_at: null,
      start_processing_time_ms: this.origin, signal_origin_processing_time_ms: this.signalOrigin,
      clock: 'performance.now()', timing: {...plan.timing}, limits: {...plan.limits},
      status: 'waiting', abort_reason: null, transitions: []};
    try {
      this.switchDisplay('off', null, null, 'initial_off');
      this.notify('waiting', this.log);
      this.handle = this.requestFrame(() => this.tick());
    } catch (error) { this.fail(error); }
    return this.log;
  }
  switchDisplay(state, plannedMs, intervalIndex, cause) {
    const executed = this.now();
    this.paint(state === 'on');
    this.log.transitions.push({state, interval_index: intervalIndex, cause,
      planned_time_ms: plannedMs, processing_time_ms: executed,
      executed_elapsed_ms: executed - this.signalOrigin,
      lateness_ms: plannedMs === null ? null : executed - this.signalOrigin - plannedMs});
  }
  tick() {
    if (!this.active) return;
    this.handle = null;
    try {
      const reason = this.checkEnvironment();
      if (reason) return this.finish('interrupted', reason);
      const elapsed = this.now() - this.signalOrigin;
      const interval = this.plan.intervals[this.next];
      const planned = interval ? interval.start_ms : this.plan.total_duration_ms;
      if (elapsed >= planned) {
        // Inspect the earliest unexecuted boundary, not only the current interval.
        // No catch-up loop: missing a boundary interrupts instead of flashing rapidly.
        if (elapsed - planned > this.plan.limits.max_transition_lateness_ms)
          return this.finish('interrupted', 'transition_late', planned);
        if (!interval) return this.finish('completed', null, planned);
        this.switchDisplay(interval.state, planned, this.next, 'scheduled');
        this.next++;
        if (this.log.status === 'waiting') { this.log.status = 'running'; this.notify('running', this.log); }
      }
      this.handle = this.requestFrame(() => this.tick());
    } catch (error) { this.fail(error); }
  }
  finish(status, reason, planned = null) {
    if (!this.active) return;
    this.active = false;
    if (this.handle !== null) this.cancelFrame(this.handle);
    this.handle = null;
    this.log.status = status; this.log.abort_reason = reason;
    try { this.switchDisplay('off', planned, null, status === 'completed' ? 'final_off' : 'forced_off'); }
    catch (error) { this.log.status = 'error'; this.log.abort_reason = `paint_error: ${error.message}`; }
    this.log.ended_at = this.wallClock();
    this.notify(this.log.status, this.log);
  }
  stop() { this.finish('stopped', 'user_stop'); }
  interrupt(reason) { this.finish('interrupted', reason); }
  fail(error) { this.finish('error', `runtime_error: ${error.message}`); }
}
