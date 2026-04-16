use std::time::Instant;
use serde::{Serialize};

#[derive(Clone, Serialize)]
pub struct TimingRecord {
    pub name: String,
    pub duration_ms: f64,
}

pub struct Timer {
    name: String,
    start: Instant,
}

impl Timer {
    pub fn new(name: &str) -> Self {
        Timer {
            name: name.to_string(),
            start: Instant::now(),
        }
    }

    pub fn end(self) -> TimingRecord {
        let duration_ms = self.start.elapsed().as_secs_f64() * 1000.0;
        TimingRecord {
            name: self.name,
            duration_ms,
        }
    }
}
