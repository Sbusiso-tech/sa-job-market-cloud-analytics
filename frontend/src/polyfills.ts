// amazon-cognito-identity-js depends on buffer@4, which reads the Node-style `global`.
const g = globalThis as typeof globalThis & { global?: typeof globalThis };
g.global ??= globalThis;

export {};
