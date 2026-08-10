const lt = require('localtunnel');

async function startTunnel() {
    while (true) {
        try {
            const tunnel = await lt({ port: 8000 });
            console.log('=== TUNNEL ACTIVE ===');
            console.log('URL:', tunnel.url);
            console.log('=====================');

            await new Promise((resolve) => {
                tunnel.on('close', () => {
                    console.log('[!] Tunnel closed, restarting in 3s...');
                    resolve();
                });
                tunnel.on('error', (err) => {
                    console.log('[!] Tunnel error:', err.message, '- restarting in 3s...');
                    resolve();
                });
            });

            await new Promise(r => setTimeout(r, 3000));
        } catch (err) {
            console.log('[!] Failed to start tunnel:', err.message, '- retrying in 5s...');
            await new Promise(r => setTimeout(r, 5000));
        }
    }
}

startTunnel();
