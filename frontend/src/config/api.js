const DEFAULT_API_BASE = 'http://localhost:8000';
const rawBase = import.meta.env.VITE_API_BASE_URL?.trim() || '';

const envBase = rawBase || (import.meta.env.DEV ? DEFAULT_API_BASE : '');
if (!envBase) {
    throw new Error(
        'VITE_API_BASE_URL is not configured. Set this environment variable in Vercel to your backend URL, for example https://<your-backend>.onrender.com'
    );
}

// Prevent trailing slash issues when concatenating endpoint paths.
export const API_BASE_URL = envBase.replace(/\/+$/, '');

export const apiUrl = (path) => {
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    return `${API_BASE_URL}${normalizedPath}`;
};
