# Project Plan: MLPlayground — Visual ML Builder for Students

## Overview
MLPlayground is a drag-and-drop machine learning platform designed for school students to visually build, train, evaluate, and deploy ML models without writing code. Users construct pipelines by connecting nodes on a canvas (import data → preprocess → train → evaluate → deploy), while a synchronized Python code panel shows the equivalent scikit-learn code in real time. Completed models can be deployed to a shareable prediction page or exported as `.joblib` files.

## Tech Stack
| Layer | Technology |
|-------|------------|
| Frontend Framework | React 18+ (TypeScript, Vite) |
| Node Editor | @xyflow/react (React Flow v12) |
| Styling | Tailwind CSS 3 |
| Code Viewer | Monaco Editor (@monaco-editor/react) |
| State Management | Zustand |
| Forms | React Hook Form + Zod |
| Backend Framework | FastAPI (Python 3.11+) |
| ML Libraries | scikit-learn, pandas, numpy |
| Database | SQLite (MVP) → PostgreSQL (production) |
| ORM | SQLAlchemy + Alembic |
| Model Serialization | joblib |
| Frontend Hosting | Vercel |
| Backend Hosting | Render / Railway |
| Testing | Vitest + React Testing Library (frontend), pytest (backend) |

---

## Phases

### Phase 1: Project Scaffold & Canvas Foundation
**Goal:** Set up monorepo, install all dependencies, render an empty React Flow canvas with a node palette sidebar and basic drag-to-canvas functionality.

#### Features:

- **Monorepo Scaffold**: Initialize project with frontend and backend directories, shared types, and tooling configs.
  - `frontend/` — Vite + React + TypeScript project
  - `backend/` — FastAPI project with Poetry/pip
  - Files to create:
    - `frontend/package.json` (deps: `@xyflow/react`, `zustand`, `tailwindcss`, `@monaco-editor/react`, `react-hook-form`, `zod`, `axios`, `react-router-dom`)
    - `frontend/vite.config.ts`
    - `frontend/tsconfig.json`
    - `frontend/tailwind.config.ts`
    - `frontend/src/main.tsx` — App entry
    - `frontend/src/App.tsx` — Router setup (`/`, `/deploy/:id`)
    - `backend/pyproject.toml` (deps: `fastapi`, `uvicorn`, `scikit-learn`, `pandas`, `numpy`, `joblib`, `sqlalchemy`, `alembic`, `python-multipart`)
    - `backend/app/main.py` — FastAPI app factory with CORS middleware

- **Zustand Flow Store**: Central state for nodes, edges, and pipeline metadata.
  - `useFlowStore()` — Zustand store with `nodes: Node[]`, `edges: Edge[]`, `onNodesChange`, `onEdgesChange`, `onConnect`, `addNode(type, position)`, `updateNodeData(id, data)`, `removeNode(id)`, `resetFlow()`
  - Files to create:
    - `frontend/src/stores/flowStore.ts`
    - `frontend/src/types/nodes.ts` — Discriminated union types for all node data: `DatasetNodeData`, `PreprocessNodeData`, `SplitNodeData`, `ModelNodeData`, `EvalNodeData`, `DeployNodeData`

- **Canvas Layout**: Main page with sidebar palette (left) and React Flow canvas (center).
  - `CanvasPage` — Full-screen layout with `<Sidebar />` and `<FlowCanvas />`
  - `FlowCanvas` — Wraps `<ReactFlow>` with background, controls, minimap
  - `Sidebar` — Lists draggable node categories: Data, Preprocessing, Model, Evaluation, Deploy
  - `SidebarItem` — Individual draggable item, sets `dataTransfer` with node type
  - `FlowCanvas.onDrop` handler — reads type from `dataTransfer`, calls `addNode(type, screenToFlowPosition(event))`
  - Files to create:
    - `frontend/src/pages/CanvasPage.tsx`
    - `frontend/src/components/canvas/FlowCanvas.tsx`
    - `frontend/src/components/sidebar/Sidebar.tsx`
    - `frontend/src/components/sidebar/SidebarItem.tsx`

- **Base Node Shell**: Reusable wrapper component for all custom nodes with consistent styling, title, info button, status indicator, and typed handles.
  - `BaseNode({ title, icon, category, infoContent, status, children })` — Card with colored header (by category), `<Handle type="target" />` top, `<Handle type="source" />` bottom, info popover on `(i)` button click
  - `InfoPopover({ title, content })` — Tooltip/popover that explains the ML concept
  - `nodeTypes` registry object defined outside components — maps string keys to React components
  - Files to create:
    - `frontend/src/components/nodes/BaseNode.tsx`
    - `frontend/src/components/nodes/InfoPopover.tsx`
    - `frontend/src/components/nodes/nodeRegistry.ts` — `const nodeTypes = { dataset: DatasetNode, ... }` (initially empty implementations)
    - `frontend/src/constants/nodeInfo.ts` — Record of educational descriptions for every node type

- **Connection Validation**: Prevent invalid edges (e.g., model → dataset) using typed handle IDs and `isValidConnection`.
  - `isValidConnection(connection: Connection): boolean` — Checks handle compatibility map and prevents cycles using `getOutgoers`
  - `HANDLE_COMPATIBILITY: Record<string, string[]>` — e.g., `{ "data-out": ["preprocess-in", "split-in"], "split-out": ["model-in"], ... }`
  - Files to create:
    - `frontend/src/utils/validation.ts`
    - `frontend/src/constants/handleTypes.ts`

#### Dependencies:
- None (first phase)

---

### Phase 2: Data Nodes — Import, Preview & Preprocessing
**Goal:** Implement the dataset import node (upload CSV or pick built-in dataset), display a data preview table, and build preprocessing nodes for missing values and feature engineering.

#### Features:

- **Dataset Node**: Upload a CSV or select a built-in dataset (Iris, Titanic, Boston Housing, Wine, Diabetes).
  - `DatasetNode` — Extends `BaseNode`; renders file upload input + dropdown for built-in datasets; on selection, calls `POST /api/datasets/upload` or `POST /api/datasets/builtin`; stores `datasetId`, column names, row count, and dtypes in node data
  - Backend endpoint `POST /api/datasets/upload` — Accepts `UploadFile`, saves to `uploads/`, returns `{ dataset_id, columns: [{name, dtype}], rows, preview: [...] }`
  - Backend endpoint `POST /api/datasets/builtin` — Accepts `{ name: string }`, loads from sklearn.datasets, returns same schema
  - Backend endpoint `GET /api/datasets/{id}/preview` — Returns first 10 rows as JSON
  - `DataPreviewPanel` — Bottom drawer/panel that shows tabular preview when a dataset node is selected
  - Files to create:
    - `frontend/src/components/nodes/DatasetNode.tsx`
    - `frontend/src/components/panels/DataPreviewPanel.tsx`
    - `backend/app/routers/datasets.py` — `upload_dataset()`, `load_builtin()`, `get_preview()`
    - `backend/app/services/dataset_service.py` — `save_upload(file) -> DatasetMeta`, `load_builtin(name) -> DatasetMeta`, `get_preview(dataset_id) -> list[dict]`
    - `backend/app/models/dataset.py` — SQLAlchemy model: `Dataset(id, name, file_path, columns_json, row_count, created_at)`
    - `backend/app/schemas/dataset.py` — Pydantic models: `DatasetUploadResponse`, `DatasetPreview`, `ColumnInfo`

- **Missing Value Node**: Configure how to handle nulls per column — drop rows, fill with mean/median/mode/constant.
  - `MissingValueNode` — Extends `BaseNode`; receives column list from upstream dataset node via store lookup; renders per-column strategy dropdown (`drop`, `mean`, `median`, `mode`, `constant`); stores config as `{ strategies: Record<string, {method, value?}> }` in node data
  - Backend: handled as part of pipeline execution (Phase 4), no standalone endpoint needed here
  - Files to create:
    - `frontend/src/components/nodes/MissingValueNode.tsx`
    - `frontend/src/utils/nodeDataPropagation.ts` — `getUpstreamColumns(nodeId): ColumnInfo[]` — walks edges backward to find the nearest dataset node's columns

- **Feature Engineering Node**: Select target column, drop columns, encode categoricals (label/one-hot), and scale numerics (standard/minmax/none).
  - `FeatureEngineeringNode` — Extends `BaseNode`; shows column list with checkboxes for include/exclude, dropdown to mark target variable, encoding dropdown per categorical column, scaling dropdown per numeric column
  - Stores config as `{ target: string, dropped: string[], encoding: Record<string, "label"|"onehot">, scaling: Record<string, "standard"|"minmax"|"none"> }`
  - Files to create:
    - `frontend/src/components/nodes/FeatureEngineeringNode.tsx`

#### Dependencies:
- Phase 1 (canvas, base node, store, validation)

---

### Phase 3: Split & Model Nodes
**Goal:** Build the train-test split node and all ML algorithm nodes with hyperparameter configuration.

#### Features:

- **Train-Test Split Node**: Configure split ratio and random seed.
  - `SplitNode` — Extends `BaseNode`; slider for `test_size` (0.1–0.5, default 0.2), number input for `random_state` (default 42), toggle for `stratify` (only if classification target detected)
  - Stores `{ test_size: number, random_state: number, stratify: boolean }` in node data
  - Files to create:
    - `frontend/src/components/nodes/SplitNode.tsx`

- **Linear Regression Node**: Hyperparameter config for linear regression.
  - `LinearRegressionNode` — Extends `BaseNode`; toggle for `fit_intercept` (default true), toggle for `normalize` (deprecated notice shown)
  - Stores `{ algorithm: "linear_regression", params: { fit_intercept: boolean } }`
  - Files to create:
    - `frontend/src/components/nodes/models/LinearRegressionNode.tsx`

- **Logistic Regression Node**: Hyperparameter config.
  - `LogisticRegressionNode` — Extends `BaseNode`; inputs: `C` (float, default 1.0), `max_iter` (int, default 100), `solver` dropdown (`lbfgs`, `liblinear`, `saga`), `penalty` dropdown (`l1`, `l2`, `elasticnet`, `none`)
  - Stores `{ algorithm: "logistic_regression", params: { C, max_iter, solver, penalty } }`
  - Files to create:
    - `frontend/src/components/nodes/models/LogisticRegressionNode.tsx`

- **Decision Tree Node**: Hyperparameter config.
  - `DecisionTreeNode` — Extends `BaseNode`; inputs: `max_depth` (int/null), `min_samples_split` (int, default 2), `min_samples_leaf` (int, default 1), `criterion` dropdown (`gini`/`entropy` for classification, `squared_error`/`absolute_error` for regression — auto-detected from upstream target type)
  - Stores `{ algorithm: "decision_tree", params: { max_depth, min_samples_split, min_samples_leaf, criterion } }`
  - Files to create:
    - `frontend/src/components/nodes/models/DecisionTreeNode.tsx`

- **Random Forest Node**: Hyperparameter config.
  - `RandomForestNode` — Extends `BaseNode`; inputs: `n_estimators` (int, default 100), `max_depth`, `min_samples_split`, `min_samples_leaf`, `criterion`, `max_features` dropdown (`sqrt`, `log2`, `None`)
  - Stores `{ algorithm: "random_forest", params: { n_estimators, max_depth, min_samples_split, min_samples_leaf, criterion, max_features } }`
  - Files to create:
    - `frontend/src/components/nodes/models/RandomForestNode.tsx`

- **SVM Node**: Hyperparameter config.
  - `SVMNode` — Extends `BaseNode`; inputs: `C` (float, default 1.0), `kernel` dropdown (`linear`, `rbf`, `poly`, `sigmoid`), `gamma` dropdown (`scale`, `auto`), `degree` (int, default 3, shown only when kernel=poly)
  - Stores `{ algorithm: "svm", params: { C, kernel, gamma, degree } }`
  - Files to create:
    - `frontend/src/components/nodes/models/SVMNode.tsx`

- **Model Node Factory**: Shared logic and common wrapper for all model nodes.
  - `ModelNodeWrapper({ algorithm, children })` — Shared frame with algorithm label, task type badge (classification/regression), and "Train" status indicator
  - `MODEL_REGISTRY` — Metadata for all supported algorithms: `{ key, label, taskTypes: ("classification"|"regression")[], defaultParams }`
  - Files to create:
    - `frontend/src/components/nodes/models/ModelNodeWrapper.tsx`
    - `frontend/src/constants/modelRegistry.ts`

#### Dependencies:
- Phase 2 (dataset and preprocessing nodes to provide upstream data context)

---

### Phase 4: Pipeline Execution Engine
**Goal:** Build the backend pipeline runner that traverses the node graph, executes each step in order, trains the model, and returns results. Add a "Run Pipeline" button to the frontend.

#### Features:

- **Pipeline Serializer**: Convert the React Flow graph into an ordered execution plan.
  - `serializePipeline(nodes: Node[], edges: Edge[]): PipelinePayload` — Topologically sorts nodes, strips UI-only fields, returns `{ steps: PipelineStep[], edges: {source, target}[] }`
  - `PipelinePayload` type: `{ steps: Array<{ id, type, data }>, edges: Array<{ source, target }> }`
  - Files to create:
    - `frontend/src/utils/pipelineSerializer.ts`
    - `frontend/src/types/pipeline.ts`

- **Backend Pipeline Runner**: Execute the ML pipeline step by step.
  - `POST /api/pipelines/run` — Accepts `PipelinePayload`, returns `{ pipeline_id, status, results: { metrics, model_id, predictions_sample } }`
  - `PipelineRunner` class:
    - `__init__(self, payload: PipelinePayload)`
    - `run(self) -> PipelineResult` — Orchestrates execution
    - `_execute_step(self, step: PipelineStep, context: dict) -> dict` — Dispatches to step handlers
    - `_load_dataset(self, step) -> pd.DataFrame`
    - `_handle_missing(self, df, config) -> pd.DataFrame`
    - `_feature_engineer(self, df, config) -> tuple[pd.DataFrame, str]` — Returns transformed df and target column name
    - `_split_data(self, df, target, config) -> tuple[X_train, X_test, y_train, y_test]`
    - `_train_model(self, algorithm, params, X_train, y_train) -> trained_model`
    - `_evaluate_model(self, model, X_test, y_test, task_type) -> dict[str, float]`
  - `ModelFactory.create(algorithm: str, params: dict) -> sklearn.base.BaseEstimator` — Maps algorithm string to scikit-learn class with params
  - Files to create:
    - `backend/app/routers/pipelines.py` — `run_pipeline()` endpoint
    - `backend/app/services/pipeline_runner.py` — `PipelineRunner` class
    - `backend/app/services/model_factory.py` — `ModelFactory` class
    - `backend/app/services/preprocessing.py` — `handle_missing_values(df, config)`, `engineer_features(df, config)`
    - `backend/app/schemas/pipeline.py` — Pydantic models: `PipelinePayload`, `PipelineStep`, `PipelineResult`
    - `backend/app/models/pipeline.py` — SQLAlchemy model: `Pipeline(id, user_session, payload_json, status, created_at)`
    - `backend/app/models/trained_model.py` — SQLAlchemy model: `TrainedModel(id, pipeline_id, algorithm, file_path, feature_names_json, target_name, task_type, metrics_json, created_at)`

- **Run Button & Status**: Trigger pipeline execution and show progress/results.
  - `RunButton` — Floating action button; onClick calls `serializePipeline()` then `POST /api/pipelines/run`; shows loading spinner during execution
  - `useFlowStore` additions: `pipelineStatus: "idle"|"running"|"success"|"error"`, `pipelineResult: PipelineResult|null`, `runPipeline()`
  - `ResultsPanel` — Slides up from bottom when pipeline completes; shows success/error and link to evaluation details
  - Files to create:
    - `frontend/src/components/canvas/RunButton.tsx`
    - `frontend/src/components/panels/ResultsPanel.tsx`
    - `frontend/src/services/api.ts` — Axios instance with `runPipeline(payload)`, `getDatasetPreview(id)`, etc.

#### Dependencies:
- Phase 2 (dataset endpoints), Phase 3 (model node configs)

---

### Phase 5: Evaluation Metrics & Visualization
**Goal:** Build the evaluation metrics node that displays all relevant metrics and visualizations after training completes.

#### Features:

- **Evaluation Metrics Node**: Display computed metrics based on task type.
  - `EvalMetricsNode` — Extends `BaseNode`; auto-populated after pipeline runs; shows classification metrics (accuracy, precision, recall, F1, support) or regression metrics (MAE, MSE, RMSE, R², Adjusted R²) in a clean card layout
  - Each metric row: label, value (rounded to 4 decimal places), and `(i)` info button explaining what the metric means in plain language
  - Files to create:
    - `frontend/src/components/nodes/EvalMetricsNode.tsx`
    - `frontend/src/constants/metricInfo.ts` — Plain-language descriptions for every metric

- **Confusion Matrix Visualization**: Render an interactive confusion matrix heatmap for classification tasks.
  - Backend addition to pipeline runner: `_compute_confusion_matrix(y_test, y_pred) -> { matrix: number[][], labels: string[] }`
  - `ConfusionMatrixChart` — Renders a color-coded grid using a lightweight chart lib or pure CSS grid; shows TP, FP, FN, TN with color intensity
  - Files to create:
    - `frontend/src/components/charts/ConfusionMatrixChart.tsx`
  - Files to modify:
    - `backend/app/services/pipeline_runner.py` — Add confusion matrix computation to `_evaluate_model`
    - `backend/app/schemas/pipeline.py` — Add `confusion_matrix` field to `PipelineResult`

- **Metrics Detail Panel**: Full-screen detail view of all metrics with explanations.
  - `MetricsDetailPanel` — Expanded panel showing all metrics in a dashboard layout; classification view: accuracy card, precision/recall/F1 table per class, confusion matrix; regression view: MAE/MSE/RMSE cards, R²/Adjusted R² cards, predicted vs actual scatter description
  - Files to create:
    - `frontend/src/components/panels/MetricsDetailPanel.tsx`

- **Backend Metrics Computation**: Comprehensive metric calculation.
  - Classification: `accuracy_score`, `precision_score(average="weighted")`, `recall_score(average="weighted")`, `f1_score(average="weighted")`, `classification_report`, `confusion_matrix`
  - Regression: `mean_absolute_error`, `mean_squared_error`, `np.sqrt(mse)` for RMSE, `r2_score`, adjusted R² via `1 - (1-r2)*(n-1)/(n-p-1)`
  - Files to modify:
    - `backend/app/services/pipeline_runner.py` — Expand `_evaluate_model` with all metrics

#### Dependencies:
- Phase 4 (pipeline runner must return raw predictions and metrics)

---

### Phase 6: Live Python Code Generation
**Goal:** Generate equivalent Python/scikit-learn code from the visual pipeline and display it in a Monaco Editor side panel that updates in real time as nodes are added or configured.

#### Features:

- **Code Generator Engine**: Traverse the pipeline graph and emit Python code for each step.
  - `generatePythonCode(nodes: Node[], edges: Edge[]): string` — Topologically sorts nodes, generates import block, then code block per node type
  - `generateImports(nodeTypes: string[]): string` — Collects unique imports (pandas, sklearn.model_selection, specific model imports, metrics imports)
  - `generateDatasetCode(data: DatasetNodeData): string` — `pd.read_csv(...)` or `from sklearn.datasets import load_iris`
  - `generateMissingValueCode(data: MissingValueNodeData): string` — `df.fillna(...)` / `df.dropna()`
  - `generateFeatureEngineeringCode(data: FeatureEngineeringNodeData): string` — `LabelEncoder`, `OneHotEncoder`, `StandardScaler`, `MinMaxScaler`
  - `generateSplitCode(data: SplitNodeData): string` — `train_test_split(...)`
  - `generateModelCode(data: ModelNodeData): string` — Model instantiation and `.fit()`
  - `generateEvalCode(data: EvalNodeData): string` — Metric calculations and print statements
  - Files to create:
    - `frontend/src/services/codeGenerator.ts`
    - `frontend/src/services/codeGenerator/imports.ts`
    - `frontend/src/services/codeGenerator/dataset.ts`
    - `frontend/src/services/codeGenerator/preprocessing.ts`
    - `frontend/src/services/codeGenerator/model.ts`
    - `frontend/src/services/codeGenerator/evaluation.ts`
    - `frontend/src/services/codeGenerator/index.ts` — Re-exports and orchestrator

- **Code Panel UI**: Toggleable right-side panel with Monaco Editor showing generated Python.
  - `CodePanel` — Slide-in panel from right edge; header with "Python Code" title and copy-to-clipboard button; renders `<MonacoEditor language="python" value={code} options={{ readOnly: true, minimap: { enabled: false } }} />`
  - `CodePanelToggle` — Floating button/tab on right edge labeled "</> Code" to open/close
  - `useFlowStore` additions: `codePanelOpen: boolean`, `toggleCodePanel()`
  - Code updates reactively: `useMemo(() => generatePythonCode(nodes, edges), [nodes, edges])`
  - Files to create:
    - `frontend/src/components/panels/CodePanel.tsx`
    - `frontend/src/components/panels/CodePanelToggle.tsx`

#### Dependencies:
- Phase 3 (all node types must be defined so code generator can handle them)

---

### Phase 7: Model Deployment & Sharing
**Goal:** Allow users to deploy a trained model to a shareable prediction page where visitors can input feature values and get predictions, and allow model export as a downloadable file.

#### Features:

- **Deploy Node**: Final node in the pipeline that triggers deployment.
  - `DeployNode` — Extends `BaseNode`; shows "Deploy Model" button (enabled only after successful training); on click calls `POST /api/deployments`; after success shows shareable URL and "Export Model" button
  - Files to create:
    - `frontend/src/components/nodes/DeployNode.tsx`

- **Backend Deployment Endpoints**: Create and serve deployments.
  - `POST /api/deployments` — Accepts `{ model_id, title, description }`, generates unique `share_id` (nanoid), saves deployment record, returns `{ deployment_id, share_url }`
  - `GET /api/deployments/{share_id}` — Returns deployment metadata: `{ title, description, feature_names, feature_types, target_name, algorithm, metrics }`
  - `POST /api/deployments/{share_id}/predict` — Accepts `{ features: Record<string, number|string> }`, loads model from disk, runs `model.predict()`, returns `{ prediction, confidence? }`
  - `GET /api/models/{model_id}/export` — Returns `.joblib` file as download
  - Files to create:
    - `backend/app/routers/deployments.py` — `create_deployment()`, `get_deployment()`, `predict()`, `export_model()`
    - `backend/app/services/deployment_service.py` — `create(model_id, title) -> Deployment`, `predict(share_id, features) -> Prediction`
    - `backend/app/models/deployment.py` — SQLAlchemy model: `Deployment(id, share_id, model_id, title, description, is_active, created_at)`
    - `backend/app/schemas/deployment.py` — Pydantic models: `DeploymentCreate`, `DeploymentResponse`, `PredictionRequest`, `PredictionResponse`

- **Prediction Page**: Public page where anyone with the link can make predictions.
  - Route: `/deploy/:shareId`
  - `PredictionPage` — Fetches deployment metadata via `GET /api/deployments/{shareId}`; renders a form with input fields auto-generated from `feature_names` and `feature_types` (number input for numeric, dropdown for categorical); submit calls `POST /api/deployments/{shareId}/predict`; shows prediction result prominently
  - `PredictionForm` — Dynamic form built from feature metadata; validates inputs with Zod schema generated from feature types
  - `PredictionResult` — Card showing predicted value, confidence (if classification), model info badge
  - Files to create:
    - `frontend/src/pages/PredictionPage.tsx`
    - `frontend/src/components/prediction/PredictionForm.tsx`
    - `frontend/src/components/prediction/PredictionResult.tsx`

- **Model Export**: Download the trained model file.
  - Export button in `DeployNode` calls `GET /api/models/{model_id}/export` and triggers browser download of `.joblib` file
  - Also add "Download Python Script" button that downloads the generated code as a `.py` file
  - Files to modify:
    - `frontend/src/components/nodes/DeployNode.tsx` — Add export buttons
    - `frontend/src/services/api.ts` — Add `exportModel(modelId)`, `downloadCode(code)`

#### Dependencies:
- Phase 4 (trained model must exist), Phase 5 (metrics to display on deployment), Phase 6 (code export)

---

### Phase 8: Database, Persistence & Polish
**Goal:** Add project save/load, database migrations, error handling, responsive layout, and final UI polish for a production-ready MVP.

#### Features:

- **Project Persistence**: Save and load pipeline projects.
  - `POST /api/projects` — Accepts `{ name, flow_json }` (serialized nodes + edges), returns `{ project_id }`
  - `GET /api/projects/{id}` — Returns saved project
  - `PUT /api/projects/{id}` — Update existing project
  - `GET /api/projects` — List user's projects (session-based for MVP)
  - `useFlowStore` additions: `projectId: string|null`, `projectName: string`, `saveProject()`, `loadProject(id)`, `isDirty: boolean`
  - Auto-save debounced to 30 seconds after last change
  - Files to create:
    - `backend/app/routers/projects.py` — CRUD endpoints
    - `backend/app/models/project.py` — SQLAlchemy model: `Project(id, session_id, name, flow_json, created_at, updated_at)`
    - `backend/app/schemas/project.py` — Pydantic models
    - `frontend/src/hooks/useAutoSave.ts`
  - Files to modify:
    - `frontend/src/stores/flowStore.ts` — Add persistence actions

- **Database Setup & Migrations**: Configure SQLAlchemy and Alembic.
  - Files to create:
    - `backend/app/database.py` — Engine, SessionLocal, Base
    - `backend/alembic.ini`
    - `backend/alembic/env.py`
    - `backend/alembic/versions/001_initial.py` — Initial migration with all tables

- **Error Handling & Validation**: Consistent error responses and frontend error boundaries.
  - Backend: `HTTPException` handlers, request validation with Pydantic, file size limits (10MB CSV), supported file type checks
  - Frontend: `ErrorBoundary` component, toast notifications for API errors, node-level error indicators (red border + message)
  - Files to create:
    - `backend/app/middleware/error_handler.py`
    - `frontend/src/components/common/ErrorBoundary.tsx`
    - `frontend/src/components/common/Toast.tsx`
    - `frontend/src/hooks/useToast.ts`

- **UI Polish**: Loading states, animations, responsive design, keyboard shortcuts.
  - Loading skeletons for data preview and metrics panels
  - Smooth panel transitions (slide in/out)
  - Keyboard shortcuts: `Ctrl+S` save, `Ctrl+Enter` run pipeline, `Ctrl+\`` toggle code panel
  - Responsive sidebar collapse on smaller screens
  - Files to create:
    - `frontend/src/components/common/Skeleton.tsx`
    - `frontend/src/hooks/useKeyboardShortcuts.ts`

#### Dependencies:
- Phase 7 (all features must exist to be polished and persisted)

---

## File Structure
```
ml-playground/
├── frontend/
│   ├── public/
│   │   └── favicon.svg
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── CanvasPage.tsx
│   │   │   └── PredictionPage.tsx
│   │   ├── stores/
│   │   │   └── flowStore.ts
│   │   ├── types/
│   │   │   ├── nodes.ts
│   │   │   └── pipeline.ts
│   │   ├── components/
│   │   │   ├── canvas/
│   │   │   │   ├── FlowCanvas.tsx
│   │   │   │   └── RunButton.tsx
│   │   │   ├── sidebar/
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   └── SidebarItem.tsx
│   │   │   ├── nodes/
│   │   │   │   ├── BaseNode.tsx
│   │   │   │   ├── InfoPopover.tsx
│   │   │   │   ├── nodeRegistry.ts
│   │   │   │   ├── DatasetNode.tsx
│   │   │   │   ├── MissingValueNode.tsx
│   │   │   │   ├── FeatureEngineeringNode.tsx
│   │   │   │   ├── SplitNode.tsx
│   │   │   │   ├── EvalMetricsNode.tsx
│   │   │   │   ├── DeployNode.tsx
│   │   │   │   └── models/
│   │   │   │       ├── ModelNodeWrapper.tsx
│   │   │   │       ├── LinearRegressionNode.tsx
│   │   │   │       ├── LogisticRegressionNode.tsx
│   │   │   │       ├── DecisionTreeNode.tsx
│   │   │   │       ├── RandomForestNode.tsx
│   │   │   │       └── SVMNode.tsx
│   │   │   ├── panels/
│   │   │   │   ├── DataPreviewPanel.tsx
│   │   │   │   ├── ResultsPanel.tsx
│   │   │   │   ├── MetricsDetailPanel.tsx
│   │   │   │   ├── CodePanel.tsx
│   │   │   │   └── CodePanelToggle.tsx
│   │   │   ├── charts/
│   │   │   │   └── ConfusionMatrixChart.tsx
│   │   │   ├── prediction/
│   │   │   │   ├── PredictionForm.tsx
│   │   │   │   └── PredictionResult.tsx
│   │   │   └── common/
│   │   │       ├── ErrorBoundary.tsx
│   │   │       ├── Toast.tsx
│   │   │       └── Skeleton.tsx
│   │   ├── services/
│   │   │   ├── api.ts
│   │   │   └── codeGenerator/
│   │   │       ├── index.ts
│   │   │       ├── imports.ts
│   │   │       ├── dataset.ts
│   │   │       ├── preprocessing.ts
│   │   │       ├── model.ts
│   │   │       └── evaluation.ts
│   │   ├── utils/
│   │   │   ├── validation.ts
│   │   │   ├── pipelineSerializer.ts
│   │   │   └── nodeDataPropagation.ts
│   │   ├── hooks/
│   │   │   ├── useToast.ts
│   │   │   ├── useAutoSave.ts
│   │   │   └── useKeyboardShortcuts.ts
│   │   └── constants/
│   │       ├── handleTypes.ts
│   │       ├── nodeInfo.ts
│   │       ├── metricInfo.ts
│   │       └── modelRegistry.ts
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── tailwind.config.ts
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── database.py
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── datasets.py
│   │   │   ├── pipelines.py
│   │   │   ├── deployments.py
│   │   │   └── projects.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── dataset_service.py
│   │   │   ├── pipeline_runner.py
│   │   │   ├── model_factory.py
│   │   │   ├── preprocessing.py
│   │   │   └── deployment_service.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── dataset.py
│   │   │   ├── pipeline.py
│   │   │   ├── trained_model.py
│   │   │   ├── deployment.py
│   │   │   └── project.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── dataset.py
│   │   │   ├── pipeline.py
│   │   │   ├── deployment.py
│   │   │   └── project.py
│   │   └── middleware/
│   │       ├── __init__.py
│   │       └── error_handler.py
│   ├── uploads/
│   ├── trained_models/
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   │       └── 001_initial.py
│   ├── tests/
│   │   ├── test_pipeline_runner.py
│   │   ├── test_model_factory.py
│   │   └── test_preprocessing.py
│   └── pyproject.toml
└── README.md
```
