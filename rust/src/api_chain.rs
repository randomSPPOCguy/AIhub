use anyhow::{Context, Result};
use pyo3::prelude::*;
use pyo3::types::{PyList, PyModule};
use serde_json::Value;
use std::path::PathBuf;

pub struct PythonBridge {
    module: Py<PyModule>,
}

impl PythonBridge {
    pub fn new() -> Result<Self> {
        Python::with_gil(|py| {
            augment_python_path(py)?;
            let module = PyModule::import(py, "ai_gateway")?;
            Ok(Self {
                module: module.into(),
            })
        })
        .map_err(|err| err.into())
    }

    pub fn generate_response(&self, query: &str, enrichment_chunks: &[String]) -> Result<String> {
        Python::with_gil(|py| {
            let module = self.module.bind(py);
            let py_list = PyList::new(py, enrichment_chunks);
            let output = module
                .getattr("generate_response")?
                .call1((query, py_list))?;
            output.extract().context("python generate_response failed")
        })
    }

    pub fn enrich_entity(&self, entity: &str, entity_type: &str) -> Result<Value> {
        Python::with_gil(|py| {
            let module = self.module.bind(py);
            let py_value = module
                .getattr("enrich_entity")?
                .call1((entity, entity_type))?;
            let serialized: String = py_value.extract()?;
            serde_json::from_str(&serialized).context("invalid enrichment payload")
        })
    }
}

fn augment_python_path(py: Python<'_>) -> PyResult<()> {
    let sys = py.import("sys")?;
    let path: &PyList = sys.getattr("path")?.downcast()?;
    let candidate = python_home();
    let candidate_str = candidate
        .to_str()
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Invalid python path"))?;
    if !path.iter().any(|entry| entry.extract::<String>().map(|s| s == candidate_str).unwrap_or(false)) {
        path.insert(0, candidate_str)?;
    }
    Ok(())
}

fn python_home() -> PathBuf {
    if let Ok(path) = std::env::var("FRANK_PYTHON_PATH") {
        return PathBuf::from(path);
    }
    let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    manifest
        .parent()
        .map(|root| root.join("python"))
        .unwrap_or_else(|| PathBuf::from("python"))
}
