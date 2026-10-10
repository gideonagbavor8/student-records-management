const studentRows = document.querySelector("#student-rows");
const studentDialog = document.querySelector("#student-dialog");
const studentForm = document.querySelector("#student-form");
const notice = document.querySelector("#notice");
const searchInput = document.querySelector("#search-input");
const courseSelect = document.querySelector("#courses");
let students = [];
let courses = [];

async function api(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  const result = response.status === 204 ? null : await response.json();
  if (!response.ok) throw new Error(result?.error || "The request could not be completed.");
  return result;
}

function showNotice(message, kind = "success") {
  notice.textContent = message;
  notice.className = `notice ${kind}`;
  notice.hidden = false;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

function renderStudents() {
  const query = searchInput.value.trim().toLocaleLowerCase();
  const visibleStudents = students.filter((student) => [
    student.first_name, student.last_name, student.student_number, student.program,
  ].some((value) => value.toLocaleLowerCase().includes(query)));
  document.querySelector("#student-count").textContent = students.length;
  document.querySelector("#course-count").textContent = courses.length;
  document.querySelector("#record-label").textContent =
    `${visibleStudents.length} ${visibleStudents.length === 1 ? "record" : "records"}`;

  if (!visibleStudents.length) {
    studentRows.innerHTML = `<tr><td class="empty-state" colspan="6">${students.length ? "No matching students found." : "No student records yet. Add a student to get started."}</td></tr>`;
    return;
  }
  studentRows.innerHTML = visibleStudents.map((student) => {
    const initials = `${student.first_name[0]}${student.last_name[0]}`.toUpperCase();
    const fullName = `${student.first_name} ${student.last_name}`;
    const courseTags = student.courses.length
      ? student.courses.map((course) => `<span class="course-tag">${escapeHtml(course)}</span>`).join("")
      : '<span class="student-email">No courses</span>';
    return `<tr>
      <td><div class="student-cell"><span class="avatar">${escapeHtml(initials)}</span><div><div class="student-name">${escapeHtml(fullName)}</div><div class="student-email">${escapeHtml(student.email)}</div></div></div></td>
      <td><span class="id-tag">${escapeHtml(student.student_number)}</span></td>
      <td><span class="program-text">${escapeHtml(student.program)}</span></td>
      <td><div class="course-list">${courseTags}</div></td>
      <td><span class="region-tag">${escapeHtml(student.region)}</span></td>
      <td><div class="row-actions">
        <button class="row-action" type="button" data-action="edit" data-id="${student.id}" aria-label="Edit ${escapeHtml(fullName)}">✎</button>
        <button class="row-action" type="button" data-action="delete" data-id="${student.id}" aria-label="Delete ${escapeHtml(fullName)}">⌫</button>
      </div></td>
    </tr>`;
  }).join("");
}

async function loadData() {
  try {
    [students, courses] = await Promise.all([api("/api/students"), api("/api/courses")]);
    courseSelect.innerHTML = courses.map((course) =>
      `<option value="${course.id}">${escapeHtml(course.code)} - ${escapeHtml(course.name)}</option>`
    ).join("");
    renderStudents();
    return true;
  } catch (error) {
    studentRows.innerHTML = '<tr><td class="empty-state" colspan="6">Student records could not be loaded.</td></tr>';
    document.querySelector("#record-label").textContent = "Unable to load";
    showNotice(error.message, "error");
    return false;
  }
}

function openForm(student = null) {
  studentForm.reset();
  document.querySelector("#form-error").hidden = true;
  document.querySelector("#student-id").value = student?.id || "";
  document.querySelector("#dialog-title").textContent = student ? "Edit student" : "Add student";
  const fieldMap = {
    "student-number": "student_number",
    "first-name": "first_name",
    "last-name": "last_name",
    email: "email",
    region: "region",
    program: "program",
  };
  for (const [field, key] of Object.entries(fieldMap)) {
    if (student) document.querySelector(`#${field}`).value = student[key] || "";
  }
  for (const option of courseSelect.options) {
    option.selected = student ? student.course_ids.includes(Number(option.value)) : false;
  }
  studentDialog.showModal();
}

document.querySelector("#add-student-button").addEventListener("click", () => openForm());
document.querySelector("#close-dialog").addEventListener("click", () => studentDialog.close());
document.querySelector("#cancel-dialog").addEventListener("click", () => studentDialog.close());
searchInput.addEventListener("input", renderStudents);

studentForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const id = document.querySelector("#student-id").value;
  const record = {
    student_number: document.querySelector("#student-number").value.trim(),
    first_name: document.querySelector("#first-name").value.trim(),
    last_name: document.querySelector("#last-name").value.trim(),
    email: document.querySelector("#email").value.trim(),
    region: document.querySelector("#region").value.trim(),
    program: document.querySelector("#program").value.trim(),
    course_ids: [...courseSelect.selectedOptions].map((option) => Number(option.value)),
  };
  try {
    await api(id ? `/api/students/${id}` : "/api/students", {
      method: id ? "PUT" : "POST",
      body: JSON.stringify(record),
    });
    studentDialog.close();
    if (await loadData()) showNotice(id ? "Student record updated." : "Student record added.");
  } catch (error) {
    const formError = document.querySelector("#form-error");
    formError.textContent = error.message;
    formError.hidden = false;
  }
});

studentRows.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const student = students.find((record) => record.id === Number(button.dataset.id));
  if (!student) return;
  if (button.dataset.action === "edit") {
    openForm(student);
    return;
  }
  if (!window.confirm(`Delete the record for ${student.first_name} ${student.last_name}?`)) return;
  try {
    await api(`/api/students/${student.id}`, { method: "DELETE" });
    if (await loadData()) showNotice("Student record deleted.");
  } catch (error) {
    showNotice(error.message, "error");
  }
});

loadData();
