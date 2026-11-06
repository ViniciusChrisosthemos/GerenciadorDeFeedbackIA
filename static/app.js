const state = {
  data: { templates: [], corrections: [] },
  selectedCorrectionId: "",
  selectedWorkItemId: "",
  phase: "phase1",
  criterionId: "",
  saving: null,
};

const $ = (selector) => document.querySelector(selector);

const elements = {
  templateForm: $("#template-form"),
  templateId: $("#template-id"),
  templateMaxGrade: $("#template-max-grade"),
  templateCriteria: $("#template-criteria"),
  correctionForm: $("#correction-form"),
  correctionId: $("#correction-id"),
  phase1Template: $("#phase1-template"),
  phase2Template: $("#phase2-template"),
  studentCount: $("#student-count"),
  correctionSelect: $("#correction-select"),
  addWorkItem: $("#add-work-item"),
  removeWorkItem: $("#remove-work-item"),
  emptyState: $("#empty-state"),
  editor: $("#editor"),
  workItemSelect: $("#work-item-select"),
  phaseButtons: [$("#phase1-button"), $("#phase2-button")],
  correctedToggle: $("#corrected-toggle"),
  zipSourceDir: $("#zip-source-dir"),
  zipDestinationDir: $("#zip-destination-dir"),
  selectZipSource: $("#select-zip-source"),
  selectZipDestination: $("#select-zip-destination"),
  importZips: $("#import-zips"),
  zipImportStatus: $("#zip-import-status"),
  studentName: $("#student-name"),
  grade: $("#grade"),
  deliveryStage: $("#delivery-stage"),
  sharedObservation: $("#shared-observation"),
  criteriaList: $("#criteria-list"),
  criterionTitle: $("#selected-criterion-title"),
  criterionComments: $("#criterion-comments"),
  commentForm: $("#comment-form"),
  commentArea: $("#comment-area"),
  commentId: $("#comment-id"),
  commentMessage: $("#comment-message"),
  headerComments: $("#header-comments"),
  footerComments: $("#footer-comments"),
  report: $("#report"),
  toast: $("#toast"),
};

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.error || "Erro ao processar solicitação.");
  }
  return body;
}

async function loadState() {
  state.data = await request("/api/state");
  state.selectedCorrectionId ||= state.data.corrections[0]?.id || "";
  render();
}

function currentCorrection() {
  return state.data.corrections.find((item) => item.id === state.selectedCorrectionId);
}

function currentTemplate() {
  const correction = currentCorrection();
  if (!correction) return null;
  const templateId = state.phase === "phase1" ? correction.phase1_template_id : correction.phase2_template_id;
  return state.data.templates.find((item) => item.id === templateId);
}

function currentWorkItem() {
  const correction = currentCorrection();
  if (!correction) return null;
  return correction.work_items.find((item) => item.id === state.selectedWorkItemId) || null;
}

function currentPhaseData() {
  return currentWorkItem()?.[state.phase] || null;
}

function firstName(fullName) {
  const name = (fullName || "").trim().split(/\s+/)[0] || "aluno";
  return name.charAt(0).toUpperCase() + name.slice(1);
}

function commentText(comments, id) {
  return comments.find((comment) => comment.id === id)?.message || "";
}

function phaseLabel() {
  return state.phase === "phase1" ? "Fase 1" : "Fase 2";
}

function workItemLabel(item, index) {
  return item.student_name?.trim() || `Aluno ${index + 1}`;
}

function isWorkItemCorrected(item, phase) {
  const phaseData = item?.[phase];
  return Boolean(phaseData?.corrected);
}

function workItemStatusLabel(item, index, phase) {
  const marker = isWorkItemCorrected(item, phase) ? "✓ Corrigido" : "○ Pendente";
  return `${marker} - ${workItemLabel(item, index)}`;
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add("show");
  window.setTimeout(() => elements.toast.classList.remove("show"), 1800);
}

function fillSelect(select, items, selectedValue, emptyText) {
  select.innerHTML = "";
  if (!items.length && emptyText) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = emptyText;
    select.append(option);
  }
  for (const item of items) {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = item.id;
    option.selected = item.id === selectedValue;
    select.append(option);
  }
}

function render() {
  fillSelect(elements.phase1Template, state.data.templates, elements.phase1Template.value);
  fillSelect(elements.phase2Template, state.data.templates, elements.phase2Template.value);
  if (!elements.phase1Template.value && state.data.templates[0]) elements.phase1Template.value = state.data.templates[0].id;
  if (!elements.phase2Template.value && state.data.templates[1]) elements.phase2Template.value = state.data.templates[1].id;

  fillSelect(elements.correctionSelect, state.data.corrections, state.selectedCorrectionId, "Nenhuma correção");

  const correction = currentCorrection();
  const hasCorrection = Boolean(correction);
  elements.emptyState.classList.toggle("hidden", hasCorrection);
  elements.editor.classList.toggle("hidden", !hasCorrection);

  if (!hasCorrection) {
    elements.addWorkItem.disabled = true;
    elements.removeWorkItem.disabled = true;
    elements.importZips.disabled = true;
    elements.correctedToggle.disabled = true;
    elements.workItemSelect.innerHTML = "";
    elements.report.value = "";
    return;
  }

  if (state.selectedWorkItemId && !correction.work_items.some((item) => item.id === state.selectedWorkItemId && item[state.phase])) {
    state.selectedWorkItemId = "";
  }
  elements.addWorkItem.disabled = false;
  elements.removeWorkItem.disabled = !state.selectedWorkItemId;
  elements.importZips.disabled = false;

  const activeTemplate = currentTemplate();
  const phaseWorkItems = correction.work_items.filter((item) => Boolean(item[state.phase]));
  const workLabels = phaseWorkItems.map((item) => ({
    id: item.id,
    label: workItemStatusLabel(item, correction.work_items.indexOf(item), state.phase),
  }));
  elements.workItemSelect.innerHTML = "";
  const emptyOption = document.createElement("option");
  emptyOption.value = "";
  emptyOption.textContent = "Selecione um aluno";
  emptyOption.selected = !state.selectedWorkItemId;
  elements.workItemSelect.append(emptyOption);
  for (const item of workLabels) {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = item.label;
    option.selected = item.id === state.selectedWorkItemId;
    elements.workItemSelect.append(option);
  }

  for (const button of elements.phaseButtons) {
    button.classList.toggle("active", button.dataset.phase === state.phase);
  }

  const workItem = currentWorkItem();
  const template = activeTemplate;
  const phaseData = currentPhaseData();
  if (!workItem || !template || !phaseData) {
    elements.workItemSelect.classList.remove("corrected", "pending");
    elements.correctedToggle.disabled = true;
    elements.correctedToggle.textContent = "Corrigido";
    clearEditor();
    elements.zipImportStatus.textContent = workItem ? "Ainda não houve inserção de trabalho nesta fase." : "";
    return;
  }
  elements.zipImportStatus.textContent = "";

  const corrected = isWorkItemCorrected(workItem, state.phase);
  elements.workItemSelect.classList.toggle("corrected", corrected);
  elements.workItemSelect.classList.toggle("pending", !corrected);
  elements.correctedToggle.disabled = false;
  elements.correctedToggle.textContent = corrected ? "Desfazer Correção" : "Corrigido";
  elements.correctedToggle.classList.toggle("pressed", corrected);

  elements.studentName.value = workItem.student_name || "";
  elements.sharedObservation.value = workItem.shared_observation || "";
  elements.grade.max = template.max_grade;
  elements.grade.value = phaseData.grade ?? 0;
  elements.deliveryStage.value = phaseData.delivery_stage || "Regular";

  if (!state.criterionId || !template.criteria.some((criterion) => criterion.id === state.criterionId)) {
    state.criterionId = template.criteria[0]?.id || "";
  }

  renderCriteria(template);
  renderComments(template, phaseData);
  renderReport(template, workItem, phaseData);
}

function clearEditor() {
  elements.criteriaList.innerHTML = "";
  elements.criterionComments.innerHTML = "";
  elements.headerComments.innerHTML = "";
  elements.footerComments.innerHTML = "";
  elements.report.value = "";
  elements.studentName.value = "";
  elements.sharedObservation.value = "";
  elements.grade.value = "";
  elements.deliveryStage.value = "Regular";
  elements.correctedToggle.classList.remove("pressed");
}

function renderCriteria(template) {
  elements.criteriaList.innerHTML = "";
  for (const criterion of template.criteria) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = criterion.id;
    button.classList.toggle("pressed", criterion.id === state.criterionId);
    button.addEventListener("click", () => {
      state.criterionId = criterion.id;
      render();
    });
    elements.criteriaList.append(button);
  }
}

function renderComments(template, phaseData) {
  const selectedCriterion = template.criteria.find((criterion) => criterion.id === state.criterionId);
  elements.criterionTitle.textContent = selectedCriterion?.id || "Critério";
  elements.criterionComments.innerHTML = "";
  if (selectedCriterion) {
    for (const comment of selectedCriterion.comments) {
      const selected = (phaseData.selected_comments[selectedCriterion.id] || []).includes(comment.id);
      elements.criterionComments.append(commentButton(comment, selected, () => {
        toggleCriterionComment(selectedCriterion.id, comment.id);
      }));
    }
  }

  elements.headerComments.innerHTML = "";
  for (const comment of template.header_comments || []) {
    const selected = (phaseData.header_comments || []).includes(comment.id);
    elements.headerComments.append(commentButton(comment, selected, () => {
      toggleListValue(phaseData.header_comments, comment.id);
      queueSaveCurrentWorkItem();
      render();
    }));
  }

  elements.footerComments.innerHTML = "";
  for (const comment of template.footer_comments || []) {
    const selected = (phaseData.footer_comments || []).includes(comment.id);
    elements.footerComments.append(commentButton(comment, selected, () => {
      toggleListValue(phaseData.footer_comments, comment.id);
      queueSaveCurrentWorkItem();
      render();
    }));
  }
}

function commentButton(comment, selected, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = comment.id;
  button.title = comment.message;
  button.classList.toggle("pressed", selected);
  button.addEventListener("click", onClick);
  return button;
}

function toggleCriterionComment(criterionId, commentId) {
  const phaseData = currentPhaseData();
  const selected = phaseData.selected_comments[criterionId] || [];
  if (commentId === "OK") {
    phaseData.selected_comments[criterionId] = ["OK"];
  } else {
    const withoutOk = selected.filter((id) => id !== "OK");
    toggleListValue(withoutOk, commentId);
    phaseData.selected_comments[criterionId] = withoutOk.length ? withoutOk : ["OK"];
  }
  queueSaveCurrentWorkItem();
  render();
}

function toggleListValue(list, value) {
  const index = list.indexOf(value);
  if (index >= 0) {
    list.splice(index, 1);
  } else {
    list.push(value);
  }
}

function renderReport(template, workItem, phaseData) {
  const lines = [
    `Olá, ${firstName(workItem.student_name)}, tudo certo?`,
    "",
  ];

  const headerTexts = (phaseData.header_comments || [])
    .map((id) => commentText(template.header_comments || [], id))
    .filter(Boolean);
  lines.push(...headerTexts);
  if (headerTexts.length) lines.push("");

  lines.push("Segue um resumo dos critérios avaliados:", "");

  template.criteria.forEach((criterion, index) => {
    lines.push(`${index + 1}. ${criterion.id}:`);
    const selected = phaseData.selected_comments[criterion.id] || [];
    selected.forEach((id, commentIndex) => {
      const text = commentText(criterion.comments, id);
      if (text) lines.push(`${String.fromCharCode(97 + commentIndex)}. ${text}`);
    });
    lines.push("");
  });

  const footerTexts = (phaseData.footer_comments || [])
    .map((id) => commentText(template.footer_comments || [], id))
    .filter(Boolean);
  lines.push(...footerTexts);
  if (footerTexts.length) lines.push("");

  lines.push("Qualquer dúvida sobre a correção, estou a disposição.", "", "Att, Vinicius C. Teixeira.");
  elements.report.value = lines.join("\n").replace(/\n{3,}/g, "\n\n");
}

function updateCurrentWorkItemFromFields() {
  const workItem = currentWorkItem();
  const phaseData = currentPhaseData();
  if (!workItem || !phaseData) return;
  const template = currentTemplate();
  const grade = Number(elements.grade.value || 0);
  workItem.student_name = elements.studentName.value;
  workItem.shared_observation = elements.sharedObservation.value;
  phaseData.grade = Math.min(Math.max(grade, 0), Number(template?.max_grade || grade));
  phaseData.delivery_stage = elements.deliveryStage.value;
}

function updateSelectedWorkOption() {
  const correction = currentCorrection();
  const workItem = currentWorkItem();
  if (!correction || !workItem) return;
  const index = correction.work_items.findIndex((item) => item.id === workItem.id);
  const option = [...elements.workItemSelect.options].find((item) => item.value === workItem.id);
  if (option) {
    option.textContent = workItemStatusLabel(workItem, index, state.phase);
  }
}

function queueSaveCurrentWorkItem() {
  updateCurrentWorkItemFromFields();
  updateSelectedWorkOption();
  const template = currentTemplate();
  const workItem = currentWorkItem();
  const phaseData = currentPhaseData();
  if (template && workItem && phaseData) {
    renderReport(template, workItem, phaseData);
  }
  window.clearTimeout(state.saving);
  state.saving = window.setTimeout(saveCurrentWorkItem, 250);
}

async function saveCurrentWorkItem() {
  const correction = currentCorrection();
  const workItem = currentWorkItem();
  if (!correction || !workItem) return;
  await request(`/api/corrections/${correction.id}/work-items/${workItem.id}`, {
    method: "PUT",
    body: JSON.stringify(workItem),
  });
}

elements.templateForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const criteria = elements.templateCriteria.value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((id) => ({ id, comments: [{ id: "OK", message: "OK" }] }));
  try {
    await request("/api/templates", {
      method: "POST",
      body: JSON.stringify({
        id: elements.templateId.value,
        max_grade: Number(elements.templateMaxGrade.value || 0),
        criteria,
        header_comments: [],
        footer_comments: [],
      }),
    });
    elements.templateForm.reset();
    elements.templateMaxGrade.value = "10";
    await loadState();
    showToast("Template criado.");
  } catch (error) {
    showToast(error.message);
  }
});

elements.correctionForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const correction = await request("/api/corrections", {
      method: "POST",
      body: JSON.stringify({
        id: elements.correctionId.value,
        phase1_template_id: elements.phase1Template.value,
        phase2_template_id: elements.phase2Template.value,
        student_count: Number(elements.studentCount.value || 1),
      }),
    });
    state.selectedCorrectionId = correction.id;
    state.selectedWorkItemId = "";
    elements.correctionForm.reset();
    elements.studentCount.value = "1";
    await loadState();
    showToast("Correção criada.");
  } catch (error) {
    showToast(error.message);
  }
});

elements.correctionSelect.addEventListener("change", () => {
  state.selectedCorrectionId = elements.correctionSelect.value;
  state.selectedWorkItemId = "";
  state.criterionId = "";
  render();
});

elements.addWorkItem.addEventListener("click", async () => {
  const correction = currentCorrection();
  if (!correction) return;
  const workItem = await request(`/api/corrections/${correction.id}/work-items`, { method: "POST" });
  state.selectedWorkItemId = workItem.id;
  await loadState();
  showToast("Aluno adicionado.");
});

elements.removeWorkItem.addEventListener("click", async () => {
  const correction = currentCorrection();
  const workItem = currentWorkItem();
  if (!correction || !workItem) return;
  await request(`/api/corrections/${correction.id}/work-items/${workItem.id}`, { method: "DELETE" });
  state.selectedWorkItemId = "";
  await loadState();
  showToast("Aluno removido.");
});

async function selectFolderInto(input) {
  elements.zipImportStatus.textContent = "Aguardando seleção da pasta...";
  const result = await request("/api/select-folder", { method: "POST", body: JSON.stringify({}) });
  if (result.path) {
    input.value = result.path;
    elements.zipImportStatus.textContent = "";
  } else {
    elements.zipImportStatus.textContent = "Nenhuma pasta selecionada. Você também pode colar ou digitar o caminho.";
  }
}

elements.selectZipSource.addEventListener("click", async () => {
  try {
    await selectFolderInto(elements.zipSourceDir);
  } catch (error) {
    showToast(error.message);
  }
});

elements.selectZipDestination.addEventListener("click", async () => {
  try {
    await selectFolderInto(elements.zipDestinationDir);
  } catch (error) {
    showToast(error.message);
  }
});

elements.importZips.addEventListener("click", async () => {
  const correction = currentCorrection();
  if (!correction) return;
  if (!elements.zipSourceDir.value || !elements.zipDestinationDir.value) {
    showToast("Selecione as duas pastas.");
    return;
  }
  elements.importZips.disabled = true;
  elements.importZips.textContent = "Processando...";
  elements.zipImportStatus.textContent = "Processando arquivos...";
  try {
    const summary = await request(`/api/corrections/${correction.id}/import-zips`, {
      method: "POST",
      body: JSON.stringify({
        source_dir: elements.zipSourceDir.value,
        destination_dir: elements.zipDestinationDir.value,
        phase: state.phase,
      }),
    });
    state.selectedWorkItemId = "";
    await loadState();
    const warning = summary.conversion_errors?.length ? " Alguns Word não foram convertidos." : "";
    elements.zipImportStatus.textContent = `${summary.zip_count} ZIPs, ${summary.loose_pdf_count} PDFs soltos, ${summary.added_students} alunos, ${summary.copied_pdfs} PDFs, ${summary.converted_word} Word convertidos, ${summary.copied_python} Python.${warning}`;
    showToast(`${summary.zip_count} ZIPs e ${summary.loose_pdf_count} PDFs processados; ${summary.added_students} alunos inseridos.${warning}`);
  } catch (error) {
    elements.zipImportStatus.textContent = error.message;
    showToast(error.message);
  } finally {
    elements.importZips.disabled = false;
    elements.importZips.textContent = "Processar Arquivos e Inserir Alunos";
  }
});

elements.workItemSelect.addEventListener("change", () => {
  state.selectedWorkItemId = elements.workItemSelect.value;
  render();
});

elements.correctedToggle.addEventListener("click", () => {
  const phaseData = currentPhaseData();
  if (!phaseData) return;
  phaseData.corrected = !Boolean(phaseData.corrected);
  queueSaveCurrentWorkItem();
  render();
});

for (const button of elements.phaseButtons) {
  button.addEventListener("click", () => {
    state.phase = button.dataset.phase;
    const selectedItem = currentWorkItem();
    if (!selectedItem?.[state.phase]) state.selectedWorkItemId = "";
    state.criterionId = "";
    render();
  });
}

for (const field of [elements.studentName, elements.grade, elements.deliveryStage, elements.sharedObservation]) {
  field.addEventListener("input", () => {
    queueSaveCurrentWorkItem();
  });
  field.addEventListener("change", () => {
    queueSaveCurrentWorkItem();
    render();
  });
}

elements.report.addEventListener("click", async () => {
  elements.report.select();
  try {
    await navigator.clipboard.writeText(elements.report.value);
    showToast("Relatório copiado.");
  } catch (error) {
    document.execCommand("copy");
    showToast("Relatório copiado.");
  }
});

elements.commentForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const template = currentTemplate();
  if (!template) return;
  try {
    await request(`/api/templates/${template.id}/comments`, {
      method: "POST",
      body: JSON.stringify({
        area: elements.commentArea.value,
        criterion_id: state.criterionId,
        id: elements.commentId.value,
        message: elements.commentMessage.value,
      }),
    });
    elements.commentId.value = "";
    elements.commentMessage.value = "";
    await loadState();
    showToast("Comentário salvo no template.");
  } catch (error) {
    showToast(error.message);
  }
});

loadState().catch((error) => showToast(error.message));
