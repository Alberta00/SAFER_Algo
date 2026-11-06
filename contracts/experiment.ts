/** File interchange contract; no dashboard or network client exists in M0/M1. */
export type Algorithm = "fifo" | "priority" | "edf";
export type Category = "EVENT" | "LIVE_STATE" | "HISTORY";
export interface ExperimentIdentity {
  mode: "simulated";
  schema_version: 1;
  algorithm: Algorithm;
  algorithm_version: string;
  engine_version: string;
  epoch_utc: string;
  run_id: string;
  scenario_id: string;
  seed: number;
  config_hash: string;
  trace_hash: string;
}
