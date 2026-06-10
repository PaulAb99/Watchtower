const CLOUD_API_BASE_URL = "http://192.168.1.148:9000";

async function request(path, options = {}) {
  const response = await fetch(`${CLOUD_API_BASE_URL}${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  let data = null;

  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    throw new Error(data?.detail || `Request failed: ${response.status}`);
  }

  return data;
}

export const cloudApi = {
  register(email, password) {
    return request("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },

  login(email, password) {
    return request("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },

  logout() {
    return request("/api/auth/logout", {
      method: "POST",
    });
  },

  me() {
    return request("/api/auth/me");
  },

  getSystems() {
    return request("/api/systems");
  },

  getSystemEvents(systemId) {
    return request(`/api/systems/${systemId}/events`);
  },

  markEventReviewed(eventId) {
    return request(`/api/events/${eventId}/reviewed`, {
      method: "POST",
    });
  },

  eventImageUrl(eventId) {
    return `${CLOUD_API_BASE_URL}/api/events/${eventId}/image`;
  },
};