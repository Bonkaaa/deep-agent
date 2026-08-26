import { join } from 'path';
import { pathToFileURL } from 'url';

process.chdir('codeql-development-mcp-server');

const serverPath = pathToFileURL(join(process.cwd(), 'server/dist/codeql-development-mcp-server.js')).href;
const { startServer } = await import(serverPath);
await startServer('stdio');
