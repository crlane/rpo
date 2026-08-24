//! Python bindings for the `rpo` git-analysis library.
//!
//! This is a private extension module: python code reaches it as
//! `rpo._rpo`, and the public API is shaped in `python/rpo/`. Every
//! function returns polars DataFrames over the Arrow C data interface,
//! so no serialization happens at the boundary.

use pyo3::create_exception;
use pyo3::exceptions::PyException;
use pyo3::prelude::*;
use pyo3_polars::PyDataFrame;
use rpo::{ActivityOptions, RepoAnalyzer, RpoError, SnapshotSelector};

create_exception!(_rpo, RpoBaseError, PyException, "Base for all rpo errors.");
create_exception!(_rpo, NotARepositoryError, RpoBaseError, "Path is not a git repository.");
create_exception!(_rpo, InvalidGlobError, RpoBaseError, "A path glob failed to parse.");
create_exception!(_rpo, RevisionNotFoundError, RpoBaseError, "Revision does not exist.");

/// Translate a library error into the most specific python exception
/// available. Panics never cross the boundary — every fallible call
/// goes through here.
fn to_py_err(e: RpoError) -> PyErr {
    let msg = e.to_string();
    match e {
        RpoError::NotARepo { .. } => NotARepositoryError::new_err(msg),
        RpoError::InvalidGlob { .. } => InvalidGlobError::new_err(msg),
        RpoError::RevisionNotFound { .. } => RevisionNotFoundError::new_err(msg),
        _ => RpoBaseError::new_err(msg),
    }
}

/// Map a python-facing snapshot name onto a [`SnapshotSelector`].
fn selector_from(name: Option<&str>, revs: Option<Vec<String>>) -> PyResult<SnapshotSelector> {
    if let Some(revs) = revs {
        return Ok(SnapshotSelector::AtRevs(revs));
    }
    Ok(match name.unwrap_or("head") {
        "head" => SnapshotSelector::Head,
        "tags" => SnapshotSelector::Tags,
        "daily" => SnapshotSelector::Daily,
        "weekly" => SnapshotSelector::Weekly,
        "monthly" => SnapshotSelector::Monthly,
        "all" => SnapshotSelector::AllCommits,
        other => {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "unknown snapshot mode {other:?} \
                 (expected one of: head, tags, daily, weekly, monthly, all)"
            )));
        }
    })
}

/// The frames produced by one walk of a repository.
///
/// `blame` and `blame_over_time` are `None` unless the corresponding
/// analysis ran.
#[pyclass(module = "rpo._rpo", frozen)]
pub struct Analysis {
    #[pyo3(get)]
    commits: PyDataFrame,
    #[pyo3(get)]
    file_changes: PyDataFrame,
    #[pyo3(get)]
    blame: Option<PyDataFrame>,
    #[pyo3(get)]
    blame_over_time: Option<PyDataFrame>,
    #[pyo3(get)]
    skipped_files: Vec<String>,
}

#[pymethods]
impl Analysis {
    fn __repr__(&self) -> String {
        format!(
            "Analysis(commits={} rows, file_changes={} rows, blame={}, blame_over_time={})",
            self.commits.0.height(),
            self.file_changes.0.height(),
            self.blame.as_ref().map_or("None".into(), |d| format!("{} rows", d.0.height())),
            self.blame_over_time
                .as_ref()
                .map_or("None".into(), |d| format!("{} rows", d.0.height())),
        )
    }
}

/// Build a configured builder from the shared keyword arguments.
fn configured(
    path: &str,
    include_globs: Option<Vec<String>>,
    exclude_globs: Option<Vec<String>>,
    ignore_merges: bool,
    first_parent_only: bool,
    ignore_bots: bool,
) -> PyResult<rpo::Builder<rpo::DefaultBackend>> {
    let activity = ActivityOptions {
        ignore_merges,
        first_parent_only,
        ignore_whitespace: false,
        ignore_bots,
    };
    let builder = RepoAnalyzer::open(path).map_err(to_py_err)?;
    Ok(builder
        .with_activity(activity)
        .with_include_globs(include_globs.unwrap_or_default())
        .with_exclude_globs(exclude_globs.unwrap_or_default()))
}

/// Walk `path` and return the commits frame.
#[pyfunction]
#[pyo3(signature = (path, *, include_globs=None, exclude_globs=None, ignore_merges=true,
                    first_parent_only=false, ignore_bots=false))]
fn commits(
    py: Python<'_>,
    path: &str,
    include_globs: Option<Vec<String>>,
    exclude_globs: Option<Vec<String>>,
    ignore_merges: bool,
    first_parent_only: bool,
    ignore_bots: bool,
) -> PyResult<PyDataFrame> {
    let b = configured(path, include_globs, exclude_globs, ignore_merges, first_parent_only, ignore_bots)?;
    let df = py.detach(|| b.commits()).map_err(to_py_err)?;
    Ok(PyDataFrame(df))
}

/// Walk `path` and return the per-file change frame.
#[pyfunction]
#[pyo3(signature = (path, *, include_globs=None, exclude_globs=None, ignore_merges=true,
                    first_parent_only=false, ignore_bots=false))]
fn file_changes(
    py: Python<'_>,
    path: &str,
    include_globs: Option<Vec<String>>,
    exclude_globs: Option<Vec<String>>,
    ignore_merges: bool,
    first_parent_only: bool,
    ignore_bots: bool,
) -> PyResult<PyDataFrame> {
    let b = configured(path, include_globs, exclude_globs, ignore_merges, first_parent_only, ignore_bots)?;
    let df = py.detach(|| b.file_changes()).map_err(to_py_err)?;
    Ok(PyDataFrame(df))
}

/// Per-line authorship at HEAD.
#[pyfunction]
#[pyo3(signature = (path, *, include_globs=None, exclude_globs=None, ignore_merges=true,
                    first_parent_only=false, ignore_bots=false))]
fn blame(
    py: Python<'_>,
    path: &str,
    include_globs: Option<Vec<String>>,
    exclude_globs: Option<Vec<String>>,
    ignore_merges: bool,
    first_parent_only: bool,
    ignore_bots: bool,
) -> PyResult<PyDataFrame> {
    let b = configured(path, include_globs, exclude_globs, ignore_merges, first_parent_only, ignore_bots)?;
    let df = py.detach(|| b.blame()).map_err(to_py_err)?;
    Ok(PyDataFrame(df))
}

/// Per-line authorship over a series of snapshots.
#[pyfunction]
#[pyo3(signature = (path, *, snapshots="monthly", revisions=None, include_globs=None,
                    exclude_globs=None, ignore_merges=true, first_parent_only=false,
                    ignore_bots=false))]
#[allow(clippy::too_many_arguments)]
fn blame_over_time(
    py: Python<'_>,
    path: &str,
    snapshots: Option<&str>,
    revisions: Option<Vec<String>>,
    include_globs: Option<Vec<String>>,
    exclude_globs: Option<Vec<String>>,
    ignore_merges: bool,
    first_parent_only: bool,
    ignore_bots: bool,
) -> PyResult<PyDataFrame> {
    let selector = selector_from(snapshots, revisions)?;
    let b = configured(path, include_globs, exclude_globs, ignore_merges, first_parent_only, ignore_bots)?;
    let df = py
        .detach(|| b.with_blame_snapshots(selector).blame_over_time())
        .map_err(to_py_err)?;
    Ok(PyDataFrame(df))
}

/// Run every terminal in one walk and return all frames.
#[pyfunction]
#[pyo3(signature = (path, *, snapshots="head", revisions=None, include_globs=None,
                    exclude_globs=None, ignore_merges=true, first_parent_only=false,
                    ignore_bots=false))]
#[allow(clippy::too_many_arguments)]
fn analyze(
    py: Python<'_>,
    path: &str,
    snapshots: Option<&str>,
    revisions: Option<Vec<String>>,
    include_globs: Option<Vec<String>>,
    exclude_globs: Option<Vec<String>>,
    ignore_merges: bool,
    first_parent_only: bool,
    ignore_bots: bool,
) -> PyResult<Analysis> {
    let selector = selector_from(snapshots, revisions)?;
    let b = configured(path, include_globs, exclude_globs, ignore_merges, first_parent_only, ignore_bots)?;
    let analysis = py
        .detach(|| b.with_blame_snapshots(selector).all())
        .map_err(to_py_err)?;
    Ok(Analysis {
        commits: PyDataFrame(analysis.commits),
        file_changes: PyDataFrame(analysis.file_changes),
        blame: analysis.blame.map(PyDataFrame),
        blame_over_time: analysis.blame_over_time.map(PyDataFrame),
        skipped_files: analysis
            .skipped_files
            .into_iter()
            .map(|s| s.path.to_string_lossy().into_owned())
            .collect(),
    })
}

#[pymodule]
fn _rpo(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__doc__", "Rust extension backing the rpo package.")?;
    m.add("RpoError", m.py().get_type::<RpoBaseError>())?;
    m.add("NotARepositoryError", m.py().get_type::<NotARepositoryError>())?;
    m.add("InvalidGlobError", m.py().get_type::<InvalidGlobError>())?;
    m.add("RevisionNotFoundError", m.py().get_type::<RevisionNotFoundError>())?;
    m.add_class::<Analysis>()?;
    m.add_function(wrap_pyfunction!(commits, m)?)?;
    m.add_function(wrap_pyfunction!(file_changes, m)?)?;
    m.add_function(wrap_pyfunction!(blame, m)?)?;
    m.add_function(wrap_pyfunction!(blame_over_time, m)?)?;
    m.add_function(wrap_pyfunction!(analyze, m)?)?;
    Ok(())
}
