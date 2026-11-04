const loginPanel = document.getElementById('loginPanel');
const galleryManager = document.getElementById('galleryManager');
const loginForm = document.getElementById('loginForm');
const projectForm = document.getElementById('projectForm');
const projectList = document.getElementById('adminProjectList');
const projectMessage = document.getElementById('projectMessage');
const loginMessage = document.getElementById('loginMessage');
const projectCount = document.getElementById('projectCount');
const imageInput = projectForm.elements.image;

let projects = [];
let editingId = null;

async function requestJson(url, options = {}) {
  const response = await fetch(url, { credentials: 'same-origin', ...options });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'The request could not be completed.');
  return data;
}

function showMessage(element, message, isError = false) {
  element.textContent = message;
  element.classList.toggle('is-error', isError);
}

function updateProjectCount() {
  projectCount.textContent = `${projects.length} ${projects.length === 1 ? 'photo' : 'photos'}`;
}

function renderProjects() {
  projectList.replaceChildren();
  updateProjectCount();

  if (projects.length === 0) {
    const emptyMessage = document.createElement('p');
    emptyMessage.className = 'admin-empty';
    emptyMessage.textContent = 'Your project gallery is empty. Add your first project photo above.';
    projectList.append(emptyMessage);
    return;
  }

  projects.forEach((project) => {
    const card = document.createElement('article');
    card.className = 'admin-project-card';

    const image = document.createElement('img');
    image.src = project.image;
    image.alt = project.alt || project.title;
    image.loading = 'lazy';

    const content = document.createElement('div');
    content.className = 'admin-project-copy';
    const category = document.createElement('p');
    category.className = 'eyebrow';
    category.textContent = project.category;
    const title = document.createElement('h3');
    title.textContent = project.title;
    const description = document.createElement('p');
    description.textContent = project.description || 'No description added.';

    const actions = document.createElement('div');
    actions.className = 'admin-project-actions';
    const editButton = document.createElement('button');
    editButton.type = 'button';
    editButton.className = 'text-link';
    editButton.textContent = 'Edit details';
    editButton.addEventListener('click', () => editProject(project));
    const deleteButton = document.createElement('button');
    deleteButton.type = 'button';
    deleteButton.className = 'text-link admin-delete-button';
    deleteButton.textContent = 'Remove';
    deleteButton.addEventListener('click', () => deleteProject(project));

    actions.append(editButton, deleteButton);
    content.append(category, title, description, actions);
    card.append(image, content);
    projectList.append(card);
  });
}

function editProject(project) {
  editingId = project.id;
  projectForm.elements.title.value = project.title;
  projectForm.elements.category.value = project.category;
  projectForm.elements.description.value = project.description || '';
  imageInput.required = false;
  document.getElementById('formHeading').textContent = 'Edit project photo';
  document.getElementById('saveProjectButton').textContent = 'Save changes';
  document.getElementById('cancelEditButton').hidden = false;
  showMessage(projectMessage, '');
  projectForm.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function resetProjectForm() {
  projectForm.reset();
  editingId = null;
  imageInput.required = true;
  document.getElementById('formHeading').textContent = 'Add a project photo';
  document.getElementById('saveProjectButton').textContent = 'Add to gallery';
  document.getElementById('cancelEditButton').hidden = true;
}

async function loadProjects() {
  projects = await requestJson('/api/projects');
  renderProjects();
}

async function deleteProject(project) {
  if (!window.confirm(`Remove "${project.title}" from the project gallery?`)) return;
  try {
    const data = await requestJson(`/api/projects/${project.id}`, { method: 'DELETE' });
    projects = data.projects;
    renderProjects();
    showMessage(projectMessage, 'Project photo removed.');
  } catch (error) {
    showMessage(projectMessage, error.message, true);
  }
}

loginForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const password = new FormData(loginForm).get('password');
  try {
    await requestJson('/api/admin/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password })
    });
    loginPanel.hidden = true;
    galleryManager.hidden = false;
    await loadProjects();
  } catch (error) {
    showMessage(loginMessage, error.message, true);
  }
});

projectForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  showMessage(projectMessage, 'Saving project photo…');
  const formData = new FormData(projectForm);
  if (!formData.get('image')?.size) formData.delete('image');

  try {
    const url = editingId ? `/api/projects/${editingId}` : '/api/projects';
    const method = editingId ? 'PUT' : 'POST';
    const data = await requestJson(url, { method, body: formData });
    if (editingId) {
      projects = projects.map((project) => project.id === data.project.id ? data.project : project);
    } else {
      projects = [data.project, ...projects];
    }
    renderProjects();
    resetProjectForm();
    showMessage(projectMessage, 'Project photo saved and published to the gallery.');
  } catch (error) {
    showMessage(projectMessage, error.message, true);
  }
});

document.getElementById('cancelEditButton').addEventListener('click', resetProjectForm);

async function initializeAdmin() {
  try {
    const session = await requestJson('/api/admin/session');
    if (session.authenticated) {
      galleryManager.hidden = false;
      await loadProjects();
    } else {
      loginPanel.hidden = false;
      document.getElementById('adminPassword').focus();
    }
  } catch (error) {
    loginPanel.hidden = false;
    showMessage(loginMessage, error.message, true);
    loginForm.hidden = true;
  }
}

initializeAdmin();
