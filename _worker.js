export default {
  async fetch(request, env) {
    const response = await env.ASSETS.fetch(request);
    if (response.status === 404) {
      return Response.redirect(new URL("/", request.url), 302);
    }
    return response;
  },
};