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
            // Import the module - Python's import system caches modules,
            // so this will only execute the module code once per process.
            // The global variables (_model, _tokenizer) will persist across
            // all calls to methods on this bridge.
            let module = PyModule::import(py, "ai_gateway")?;
            Ok(Self {
                module: module.into(),
            })
        })
        .map_err(|err: PyErr| err.into())
    }

    pub fn generate_response(&self, query: &str, enrichment_chunks: &[String], clean_output: bool) -> Result<String> {
        Python::with_gil(|py| {
            let module = self.module.as_ref(py);
            let py_list = PyList::new(py, enrichment_chunks);
            let kwargs = pyo3::types::PyDict::new(py);
            kwargs.set_item("clean_output", clean_output)?;
            let output = module
                .getattr("generate_response")?
                .call((query, py_list), Some(kwargs))?;
            output.extract().context("python generate_response failed")
        })
    }

    pub fn enrich_entity(&self, entity: &str, entity_type: &str) -> Result<Value> {
        Python::with_gil(|py| {
            let module = self.module.as_ref(py);
            let py_value = module
                .getattr("enrich_entity")?
                .call1((entity, entity_type))?;
            let serialized: String = py_value.extract()?;
            serde_json::from_str(&serialized).context("invalid enrichment payload")
        })
    }

    pub fn warmup_model(&self) -> Result<String> {
        Python::with_gil(|py| {
            let module = self.module.as_ref(py);
            let output = module
                .getattr("warmup_model")?
                .call0()?;
            output.extract().context("python warmup_model failed")
        })
    }

    pub fn generate_response_with_model(
        &self,
        query: &str,
        enrichment_chunks: &[String],
        model_type: &str,
        model_name: &str,
        api_key: &str,
        temperature: f32,
        max_tokens: u32,
        system_prompt: &str,
        clean_output: bool,
    ) -> Result<String> {
        Python::with_gil(|py| {
            let module = self.module.as_ref(py);
            let py_list = PyList::new(py, enrichment_chunks);
            let kwargs = pyo3::types::PyDict::new(py);
            kwargs.set_item("clean_output", clean_output)?;
            let output = module
                .getattr("generate_response_with_model")?
                .call((
                    query,
                    py_list,
                    model_type,
                    model_name,
                    api_key,
                    temperature,
                    max_tokens,
                    system_prompt,
                ), Some(kwargs))?;
            output.extract().context("python generate_response_with_model failed")
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
