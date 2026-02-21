import { defineConfig } from 'vite';

export default defineConfig({
    root: '.',
    base: process.env.VITE_BASE || './',
    build: {
        outDir: 'dist',
        sourcemap: true,
    },
    server: {
        port: 3000,
        open: true
    }
});
