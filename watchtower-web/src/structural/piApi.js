export function createPiApi(baseUrl) {
  async function get(path) {
    const res = await fetch(`${baseUrl}${path}`);

    if (!res.ok) {
      throw new Error(`GET ${path} failed`);
    }

    return res.json();
  }

  async function post(path, body = null) {
    const options = {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    };

    if (body) {
      options.body = JSON.stringify(body);
    }

    const res = await fetch(`${baseUrl}${path}`, options);

    if (!res.ok) {
      throw new Error(`POST ${path} failed`);
    }

    return res.json();
  }

  return {
    getStatus: () => get("/status"),

    setManual: () => post("/mode/manual"),
    setFollow: () => post("/mode/follow"),

    moveLeft: (step) => post("/servo/left", { step }),
    moveRight: (step) => post("/servo/right", { step }),
    moveUp: (step) => post("/servo/up", { step }),
    moveDown: (step) => post("/servo/down", { step }),
    center: () => post("/servo/center"),

    videoFeedUrl: () => `${baseUrl}/video_feed`,
  };
}