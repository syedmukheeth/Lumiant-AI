/** Hand a question to the assistant: a link when navigating there, an event when it is already on screen. */
export const ASK_EVENT = "lumiant:ask";

export const assistantHref = (question: string) => `/assistant?q=${encodeURIComponent(question)}`;

export const askOnPage = (question: string) => window.dispatchEvent(new CustomEvent<string>(ASK_EVENT, { detail: question }));
