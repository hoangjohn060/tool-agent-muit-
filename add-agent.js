const fs = require('fs');
const path = require('path');
const readline = require('readline');

// Configuration Paths
const OPENCLAW_CONFIG_PATH = path.join(process.env.USERPROFILE, '.openclaw', 'openclaw.json');
const AUTH_PROFILES_PATH = path.join(process.env.USERPROFILE, '.openclaw', 'auth-profiles.json');

const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
});

const question = (query) => new Promise((resolve) => rl.question(query, resolve));

async function main() {
    console.log("=== OpenClaw Agent Configuration Tool ===");

    // 1. Load Configurations
    let openclawConfig, authProfiles;
    try {
        if (fs.existsSync(OPENCLAW_CONFIG_PATH)) {
            let content = fs.readFileSync(OPENCLAW_CONFIG_PATH, 'utf8');
            if (content.charCodeAt(0) === 0xFEFF) content = content.slice(1);
            openclawConfig = JSON.parse(content);
        } else {
            console.error(`Error: ${OPENCLAW_CONFIG_PATH} not found.`);
            process.exit(1);
        }

        if (fs.existsSync(AUTH_PROFILES_PATH)) {
            let content = fs.readFileSync(AUTH_PROFILES_PATH, 'utf8');
            if (content.charCodeAt(0) === 0xFEFF) content = content.slice(1);
            authProfiles = JSON.parse(content);
        } else {
            // Create basic structure if missing
            authProfiles = { version: 1, profiles: {}, lastGood: {} };
        }
    } catch (error) {
        console.error("Error reading configuration files:", error.message);
        process.exit(1);
    }

    // 2. Gather User Input
    const agentName = await question("Enter new Agent Name (e.g., reviewer, coder): ");
    if (!agentName) { console.error("Agent name required."); process.exit(1); }

    const modelId = await question(`Enter Model ID for '${agentName}' (default: google/gemini-pro): `) || "google/gemini-pro";
    const provider = await question(`Enter Provider Name (default: google): `) || "google";

    const needApiKey = await question("Do you want to add/update the API key for this provider? (y/n): ");
    let apiKey = null;
    if (needApiKey.toLowerCase() === 'y') {
        apiKey = await question(`Enter API Key for '${provider}': `);
    }

    // 3. Update auth-profiles.json
    // We use a simple naming convention: provider:default or provider:agentName
    const profileName = `${provider}:${agentName}`; // Unique profile for this agent

    if (apiKey) {
        authProfiles.profiles[profileName] = {
            type: "api_key",
            provider: provider,
            key: apiKey,
            apiKey: apiKey // Redundant but consistent with some formats
        };

        // Update lastGood as default for this provider if not set
        if (!authProfiles.lastGood[provider]) {
            authProfiles.lastGood[provider] = profileName;
        }

        console.log(`\n[+] Updated auth profile: ${profileName}`);
    }

    // 4. Update openclaw.json
    // Add agent definition
    if (!openclawConfig.agents) openclawConfig.agents = {};

    // Create or update the specific agent entry if it's not 'defaults'
    // Note: OpenClaw often uses 'defaults' for the main. If adding a secondary, we might need a specific structure.
    // Based on standard patterns, named agents usually go under 'agents' key parallel to 'defaults' or inside a collection.
    // However, looking at the file, 'agents' has 'defaults'. Let's assume we can add 'reviewer': { ... } parallel to 'defaults'.

    openclawConfig.agents[agentName] = {
        model: {
            primary: modelId
        },
        // You might want to override workspace or other settings here
    };

    // Ensure the model is listed in 'models' whitelist/config if needed
    if (!openclawConfig.agents.defaults.models) openclawConfig.agents.defaults.models = {};
    if (!openclawConfig.agents.defaults.models[modelId]) {
        openclawConfig.agents.defaults.models[modelId] = {};
    }

    // Update Auth references in openclaw.json 'auth' section
    if (!openclawConfig.auth) openclawConfig.auth = { profiles: {} };
    if (!openclawConfig.auth.profiles) openclawConfig.auth.profiles = {};

    // Link the auth profile we just created/verified
    openclawConfig.auth.profiles[profileName] = {
        provider: provider,
        mode: "api_key" // Assuming api_key mode
    };

    console.log(`[+] Updated agent config: ${agentName} -> ${modelId}`);

    // 5. Save Changes
    try {
        // Backup first
        fs.copyFileSync(OPENCLAW_CONFIG_PATH, OPENCLAW_CONFIG_PATH + '.bak');
        fs.copyFileSync(AUTH_PROFILES_PATH, AUTH_PROFILES_PATH + '.bak');

        fs.writeFileSync(OPENCLAW_CONFIG_PATH, JSON.stringify(openclawConfig, null, 2));
        fs.writeFileSync(AUTH_PROFILES_PATH, JSON.stringify(authProfiles, null, 2));

        console.log("\nSuccess! Configuration updated.");
        console.log(`Backups created at *.bak`);
    } catch (err) {
        console.error("Error writing files:", err);
    }

    rl.close();
}

main();
