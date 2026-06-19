# Plan: Manual Model Selection

## Goal
Remove automatic models folder scanning. Allow users to manually add text models and mmproj (visual) models via file dialogs.

## Changes to llama.py

### 1. Remove ModelScanner class (lines 135-166)
Delete the entire ModelScanner class that scans MODELS_DIR for .gguf files.

### 2. Add model path storage in AppSettings
Add to AppSettings._DEFAULTS:
- text_models: [] - list of text model file paths
- mmproj_models: [] - list of mmproj model file paths

### 3. Add Add text model button in deploy page
- Insert a button next to the Text model label
- On click: open QFileDialog.getOpenFileNames() filtering for *.gguf
- Filter out files with mmproj in the name
- Append selected paths to _settings._data[text_models] and save
- Refresh the model combo box

### 4. Add Add visual model button in deploy page
- Insert a button next to the Visual model label
- On click: open QFileDialog.getOpenFileNames() filtering for *.gguf
- Filter for files with mmproj in the name (or let user choose)
- Append to _settings._data[mmproj_models] and save
- Refresh the mmproj combo box

### 5. Display selected models with remove option
- Show selected models in a list below the combo boxes
- Each item shows filename and has a remove button
- On remove: delete from settings and refresh

### 6. Update _scan_models method
- Replace ModelScanner.scan_text_models() with reading from settings
- Replace ModelScanner.scan_mmproj_models() with reading from settings
- Build model info dicts from stored paths

### 7. Update _on_model_select_internal
- Build config from the selected model file path

## UI Layout Changes
In _build_deploy_page, modify the row1 layout:
- [文本模型:] [ComboBox] [添加模型 ▼]
- [视觉模型:] [勾选] [ComboBox] [添加模型 ▼]
- [模型列表 - 显示已选中的模型文件，带删除按钮]

## Files to modify
- llama.py - all changes above

## Settings format in settings.json
{
  text_models: [...],
  mmproj_models: [...]
}
