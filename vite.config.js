import { defineConfig } from 'vite';

export default defineConfig({
    root: '.',     // Valid since index.html will be in root
    base: './',    // Relative paths for simple deployment
    build: {
        outDir: 'dist',
        sourcemap: true,
    },
    server: {
        port: 3000,
        open: true
    }
});
