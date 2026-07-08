package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestNormalizeAPIBaseURL(t *testing.T) {
	cases := map[string]string{
		"http://localhost:3001":        "http://localhost:3001/api/v1",
		"http://localhost:8000/api":    "http://localhost:8000/api/v1",
		"http://localhost:8000/api/v1": "http://localhost:8000/api/v1",
	}
	for input, expected := range cases {
		actual, err := normalizeAPIBaseURL(input)
		if err != nil {
			t.Fatalf("normalizeAPIBaseURL(%q) returned error: %v", input, err)
		}
		if actual != expected {
			t.Fatalf("normalizeAPIBaseURL(%q) = %q, want %q", input, actual, expected)
		}
	}
}

func TestConfigureLogsInAndWritesConfig(t *testing.T) {
	var loginCalled bool
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/v1/admin/login" {
			t.Fatalf("unexpected path: %s", r.URL.Path)
		}
		loginCalled = true
		_ = json.NewEncoder(w).Encode(map[string]any{"access_token": "new-token", "token_type": "bearer"})
	}))
	defer server.Close()

	configPath := filepath.Join(t.TempDir(), "config.yaml")
	code, stdout, stderr := runForTest([]string{
		"configure",
		"--server-url", server.URL,
		"--username", "admin",
		"--password", "secret",
		"--config", configPath,
	})
	if code != 0 {
		t.Fatalf("code=%d stderr=%s", code, stderr)
	}
	if !loginCalled {
		t.Fatal("login was not called")
	}
	if !strings.Contains(stdout, `"token_stored": true`) {
		t.Fatalf("unexpected stdout: %s", stdout)
	}
	values, _, err := readConfig(configPath)
	if err != nil {
		t.Fatal(err)
	}
	if values["token"] != "new-token" {
		t.Fatalf("token = %q", values["token"])
	}
	info, err := os.Stat(configPath)
	if err != nil {
		t.Fatal(err)
	}
	if info.Mode().Perm() != 0o600 {
		t.Fatalf("mode = %v, want 0600", info.Mode().Perm())
	}
}

func TestPluginShowResolvesPluginKey(t *testing.T) {
	seen := []string{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.Path)
		if r.Header.Get("Authorization") != "Bearer token" {
			t.Fatalf("missing auth header: %q", r.Header.Get("Authorization"))
		}
		switch r.URL.Path {
		case "/api/v1/admin/plugins":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"items": []map[string]any{{
					"id":         "11111111-1111-1111-1111-111111111111",
					"plugin_key": "astrbot-plugin-demo",
				}},
				"total": 1, "page": 1, "page_size": 100,
			})
		case "/api/v1/admin/plugins/11111111-1111-1111-1111-111111111111":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"id":         "11111111-1111-1111-1111-111111111111",
				"plugin_key": "astrbot-plugin-demo",
				"versions":   []any{},
			})
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	code, stdout, stderr := runForTest([]string{
		"plugin", "show", "astrbot-plugin-demo",
		"--server-url", server.URL,
		"--token", "token",
	})
	if code != 0 {
		t.Fatalf("code=%d stderr=%s", code, stderr)
	}
	if !strings.Contains(stdout, `"plugin_key": "astrbot-plugin-demo"`) {
		t.Fatalf("unexpected stdout: %s", stdout)
	}
	want := []string{"GET /api/v1/admin/plugins", "GET /api/v1/admin/plugins/11111111-1111-1111-1111-111111111111"}
	if strings.Join(seen, ",") != strings.Join(want, ",") {
		t.Fatalf("seen=%v want=%v", seen, want)
	}
}

func TestDeleteRequiresYesBeforeRequest(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		t.Fatalf("unexpected request: %s %s", r.Method, r.URL.Path)
	}))
	defer server.Close()

	code, stdout, stderr := runForTest([]string{
		"plugin", "delete", "astrbot-plugin-demo",
		"--server-url", server.URL,
		"--token", "token",
	})
	if stdout != "" {
		t.Fatalf("stdout=%s", stdout)
	}
	if code != exitConfirmationRequired {
		t.Fatalf("code=%d stderr=%s", code, stderr)
	}
	if !strings.Contains(stderr, `"code": 3`) {
		t.Fatalf("unexpected stderr: %s", stderr)
	}
}

func TestVersionDeleteRequiresYesBeforeRequest(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		t.Fatalf("unexpected request: %s %s", r.Method, r.URL.Path)
	}))
	defer server.Close()

	code, stdout, stderr := runForTest([]string{
		"plugin", "version", "delete", "astrbot-plugin-demo",
		"--version", "v1.0.0",
		"--server-url", server.URL,
		"--token", "token",
	})
	if stdout != "" {
		t.Fatalf("stdout=%s", stdout)
	}
	if code != exitConfirmationRequired {
		t.Fatalf("code=%d stderr=%s", code, stderr)
	}
}

func TestIDFlagReplacesPluginPositional(t *testing.T) {
	pluginID := "11111111-1111-1111-1111-111111111111"
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPut || r.URL.Path != "/api/v1/admin/plugins/"+pluginID+"/status" {
			t.Fatalf("unexpected request: %s %s", r.Method, r.URL.Path)
		}
		var body map[string]any
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Fatal(err)
		}
		if body["status"] != "disabled" {
			t.Fatalf("body=%v", body)
		}
		_ = json.NewEncoder(w).Encode(map[string]string{"status": "updated"})
	}))
	defer server.Close()

	code, stdout, stderr := runForTest([]string{
		"plugin", "set-status",
		"--id", pluginID,
		"--status", "disabled",
		"--server-url", server.URL,
		"--token", "token",
	})
	if code != 0 {
		t.Fatalf("code=%d stderr=%s", code, stderr)
	}
	if !strings.Contains(stdout, `"status": "updated"`) {
		t.Fatalf("unexpected stdout: %s", stdout)
	}
}

func TestVersionScanWaitsForProviderCompletion(t *testing.T) {
	pluginID := "11111111-1111-1111-1111-111111111111"
	versionID := "22222222-2222-2222-2222-222222222222"
	detailCalls := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.Method == http.MethodGet && r.URL.Path == "/api/v1/admin/plugins":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"items": []map[string]any{{
					"id":         pluginID,
					"plugin_key": "astrbot-plugin-demo",
				}},
				"total": 1, "page": 1, "page_size": 100,
			})
		case r.Method == http.MethodGet && r.URL.Path == "/api/v1/admin/plugins/"+pluginID+"/versions":
			_ = json.NewEncoder(w).Encode([]map[string]any{{
				"id":           versionID,
				"version":      "v1.0.0",
				"build_status": "success",
			}})
		case r.Method == http.MethodPost && r.URL.Path == "/api/v1/admin/plugins/"+pluginID+"/versions/"+versionID+"/scans/llm_agent/run":
			_ = json.NewEncoder(w).Encode(map[string]string{"status": "queued"})
		case r.Method == http.MethodGet && r.URL.Path == "/api/v1/admin/plugins/"+pluginID:
			detailCalls++
			mode := "pending"
			var passed any
			if detailCalls > 1 {
				mode = "real"
				passed = true
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"id":         pluginID,
				"plugin_key": "astrbot-plugin-demo",
				"versions": []map[string]any{{
					"id":           versionID,
					"version":      "v1.0.0",
					"build_status": "success",
					"scan": map[string]any{
						"llm_agent": map[string]any{
							"mode": mode,
							"pass": passed,
							"msg":  "scan state",
						},
					},
				}},
			})
		default:
			t.Fatalf("unexpected request: %s %s", r.Method, r.URL.Path)
		}
	}))
	defer server.Close()

	code, stdout, stderr := runForTest([]string{
		"plugin", "version", "scan", "run", "astrbot-plugin-demo",
		"--version", "v1.0.0",
		"--provider", "llm_agent",
		"--wait",
		"--wait-interval", "1ms",
		"--wait-timeout", "1s",
		"--server-url", server.URL,
		"--token", "token",
	})
	if code != 0 {
		t.Fatalf("code=%d stderr=%s", code, stderr)
	}
	if detailCalls < 2 {
		t.Fatalf("detailCalls=%d, want at least 2", detailCalls)
	}
	var payload map[string]any
	if err := json.Unmarshal([]byte(stdout), &payload); err != nil {
		t.Fatalf("stdout is not JSON: %v\n%s", err, stdout)
	}
	wait, ok := payload["wait"].(map[string]any)
	if !ok || wait["status"] != "success" {
		t.Fatalf("unexpected wait payload: %v", payload["wait"])
	}
	providers, ok := wait["providers"].([]any)
	if !ok || len(providers) != 1 || providers[0] != "llm_agent" {
		t.Fatalf("unexpected providers: %v", wait["providers"])
	}
}

func TestConfigProvidersEnablePreservesExistingProviders(t *testing.T) {
	var putBody map[string]any
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Authorization") != "Bearer token" {
			t.Fatalf("missing auth header: %q", r.Header.Get("Authorization"))
		}
		switch {
		case r.Method == http.MethodGet && r.URL.Path == "/api/v1/admin/config":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"values": map[string]string{},
				"effective_values": map[string]string{
					"SCAN_ENABLED_PROVIDERS": "virustotal,llm_agent",
				},
			})
		case r.Method == http.MethodPut && r.URL.Path == "/api/v1/admin/config":
			if err := json.NewDecoder(r.Body).Decode(&putBody); err != nil {
				t.Fatal(err)
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"values": map[string]string{
					"SCAN_ENABLED_PROVIDERS": "virustotal,llm_agent,clamav",
				},
				"effective_values": map[string]string{
					"SCAN_ENABLED_PROVIDERS": "virustotal,llm_agent,clamav",
				},
			})
		default:
			t.Fatalf("unexpected request: %s %s", r.Method, r.URL.Path)
		}
	}))
	defer server.Close()

	code, stdout, stderr := runForTest([]string{
		"config", "providers", "enable", "clamav",
		"--server-url", server.URL,
		"--token", "token",
	})
	if code != 0 {
		t.Fatalf("code=%d stderr=%s", code, stderr)
	}
	values := putBody["values"].(map[string]any)
	if values["SCAN_ENABLED_PROVIDERS"] != "virustotal,llm_agent,clamav" {
		t.Fatalf("unexpected providers value: %v", values["SCAN_ENABLED_PROVIDERS"])
	}
	if !strings.Contains(stdout, `"enabled": [`) || !strings.Contains(stdout, `"clamav"`) {
		t.Fatalf("unexpected stdout: %s", stdout)
	}
}

func TestTaskListSendsFilters(t *testing.T) {
	var seenQuery string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet || r.URL.Path != "/api/v1/admin/tasks" {
			t.Fatalf("unexpected request: %s %s", r.Method, r.URL.Path)
		}
		seenQuery = r.URL.RawQuery
		_ = json.NewEncoder(w).Encode(map[string]any{
			"items": []map[string]any{{
				"id":        "task-1",
				"task_type": "scan",
				"status":    "dead",
			}},
			"total": 1, "page": 1, "page_size": 20,
		})
	}))
	defer server.Close()

	code, stdout, stderr := runForTest([]string{
		"task", "list",
		"--status", "dead",
		"--type", "scan",
		"--page-size", "20",
		"--server-url", server.URL,
		"--token", "token",
	})
	if code != 0 {
		t.Fatalf("code=%d stderr=%s", code, stderr)
	}
	if !strings.Contains(seenQuery, "status=dead") || !strings.Contains(seenQuery, "type=scan") {
		t.Fatalf("unexpected query: %s", seenQuery)
	}
	if !strings.Contains(stdout, `"task_type": "scan"`) {
		t.Fatalf("unexpected stdout: %s", stdout)
	}
}

func TestWorkerStatusCommand(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet || r.URL.Path != "/api/v1/admin/worker/status" {
			t.Fatalf("unexpected request: %s %s", r.Method, r.URL.Path)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"redis_connected":    true,
			"queue_length":       1,
			"delayed_length":     0,
			"dead_letter_length": 0,
			"active_workers":     []map[string]any{},
			"tasks_by_status":    map[string]any{"queued": 1},
		})
	}))
	defer server.Close()

	code, stdout, stderr := runForTest([]string{
		"worker", "status",
		"--server-url", server.URL,
		"--token", "token",
	})
	if code != 0 {
		t.Fatalf("code=%d stderr=%s", code, stderr)
	}
	if !strings.Contains(stdout, `"queue_length": 1`) {
		t.Fatalf("unexpected stdout: %s", stdout)
	}
}

func TestConfigProvidersDisableRemovesOnlySelectedProvider(t *testing.T) {
	var putBody map[string]any
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.Method == http.MethodGet && r.URL.Path == "/api/v1/admin/config":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"effective_values": map[string]string{
					"SCAN_ENABLED_PROVIDERS": "virustotal,llm_agent,clamav",
				},
			})
		case r.Method == http.MethodPut && r.URL.Path == "/api/v1/admin/config":
			if err := json.NewDecoder(r.Body).Decode(&putBody); err != nil {
				t.Fatal(err)
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"effective_values": map[string]string{
					"SCAN_ENABLED_PROVIDERS": "virustotal,clamav",
				},
			})
		default:
			t.Fatalf("unexpected request: %s %s", r.Method, r.URL.Path)
		}
	}))
	defer server.Close()

	code, _, stderr := runForTest([]string{
		"config", "providers", "disable", "llm_agent",
		"--server-url", server.URL,
		"--token", "token",
	})
	if code != 0 {
		t.Fatalf("code=%d stderr=%s", code, stderr)
	}
	values := putBody["values"].(map[string]any)
	if values["SCAN_ENABLED_PROVIDERS"] != "virustotal,clamav" {
		t.Fatalf("unexpected providers value: %v", values["SCAN_ENABLED_PROVIDERS"])
	}
}

func TestConfigProvidersRejectsUnsupportedProvider(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodGet && r.URL.Path == "/api/v1/admin/config" {
			_ = json.NewEncoder(w).Encode(map[string]any{
				"effective_values": map[string]string{
					"SCAN_ENABLED_PROVIDERS": "virustotal",
				},
			})
			return
		}
		t.Fatalf("unexpected request: %s %s", r.Method, r.URL.Path)
	}))
	defer server.Close()

	code, _, stderr := runForTest([]string{
		"config", "providers", "enable", "unknown",
		"--server-url", server.URL,
		"--token", "token",
	})
	if code != exitValidation {
		t.Fatalf("code=%d stderr=%s", code, stderr)
	}
	if !strings.Contains(stderr, "unsupported scan provider") {
		t.Fatalf("unexpected stderr: %s", stderr)
	}
}

func TestRepoInspectSendsProviderPayload(t *testing.T) {
	var body map[string]any
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || r.URL.Path != "/api/v1/admin/plugins/inspect-repo" {
			t.Fatalf("unexpected request: %s %s", r.Method, r.URL.Path)
		}
		if r.Header.Get("Authorization") != "Bearer admin-token" {
			t.Fatalf("missing auth header: %q", r.Header.Get("Authorization"))
		}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Fatal(err)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"repo_url":          body["repo_url"],
			"selected_ref_type": body["ref_type"],
			"selected_ref":      body["ref"],
		})
	}))
	defer server.Close()

	code, stdout, stderr := runForTest([]string{
		"plugin", "inspect-repo",
		"--repo-url", "https://github.com/org/repo",
		"--ref-type", "branch",
		"--ref", "main",
		"--github-token", "github-token",
		"--credential-id", "repo-credential",
		"--include-refs", "false",
		"--server-url", server.URL,
		"--token", "admin-token",
	})
	if code != 0 {
		t.Fatalf("code=%d stderr=%s", code, stderr)
	}
	if body["repo_url"] != "https://github.com/org/repo" ||
		body["ref_type"] != "branch" ||
		body["ref"] != "main" ||
		body["temporary_token"] != "github-token" ||
		body["credential_id"] != "repo-credential" ||
		body["include_refs"] != false {
		t.Fatalf("unexpected body: %v", body)
	}
	if !strings.Contains(stdout, `"selected_ref": "main"`) {
		t.Fatalf("unexpected stdout: %s", stdout)
	}
}

func TestRepoResolveSendsMinimalPayload(t *testing.T) {
	var body map[string]any
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || r.URL.Path != "/api/v1/admin/plugins/resolve-ref" {
			t.Fatalf("unexpected request: %s %s", r.Method, r.URL.Path)
		}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Fatal(err)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"selected_ref_type": "default",
			"selected_ref":      "main",
		})
	}))
	defer server.Close()

	code, stdout, stderr := runForTest([]string{
		"plugin", "resolve-ref",
		"--repo-url", "https://github.com/org/repo",
		"--server-url", server.URL,
		"--token", "admin-token",
	})
	if code != 0 {
		t.Fatalf("code=%d stderr=%s", code, stderr)
	}
	if body["repo_url"] != "https://github.com/org/repo" {
		t.Fatalf("unexpected body: %v", body)
	}
	if _, ok := body["include_refs"]; ok {
		t.Fatalf("resolve-ref should not send include_refs: %v", body)
	}
	if !strings.Contains(stdout, `"selected_ref_type": "default"`) {
		t.Fatalf("unexpected stdout: %s", stdout)
	}
}

func TestPluginSubmitSendsGitCredentialsAndChangelog(t *testing.T) {
	var body map[string]any
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || r.URL.Path != "/api/v1/admin/plugins" {
			t.Fatalf("unexpected request: %s %s", r.Method, r.URL.Path)
		}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Fatal(err)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"status": "queued", "plugin_id": "plugin-1"})
	}))
	defer server.Close()

	code, _, stderr := runForTest([]string{
		"plugin", "submit",
		"--repo-url", "https://github.com/org/repo",
		"--version", "v1.2.3",
		"--ref", "main",
		"--changelog", "release notes",
		"--github-token", "github-token",
		"--credential-id", "repo-credential",
		"--server-url", server.URL,
		"--token", "admin-token",
	})
	if code != 0 {
		t.Fatalf("code=%d stderr=%s", code, stderr)
	}
	if body["version"] != "v1.2.3" ||
		body["ref"] != "main" ||
		body["changelog"] != "release notes" ||
		body["temporary_token"] != "github-token" ||
		body["credential_id"] != "repo-credential" {
		t.Fatalf("unexpected body: %v", body)
	}
}

func TestPluginBuildSendsGitCredentialsAndChangelog(t *testing.T) {
	pluginID := "11111111-1111-1111-1111-111111111111"
	var body map[string]any
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.Method == http.MethodGet && r.URL.Path == "/api/v1/admin/plugins":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"items": []map[string]any{{"id": pluginID, "plugin_key": "astrbot-plugin-demo"}},
				"total": 1, "page": 1, "page_size": 100,
			})
		case r.Method == http.MethodPost && r.URL.Path == "/api/v1/admin/plugins/"+pluginID+"/build":
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				t.Fatal(err)
			}
			_ = json.NewEncoder(w).Encode(map[string]any{"status": "queued"})
		default:
			t.Fatalf("unexpected request: %s %s", r.Method, r.URL.Path)
		}
	}))
	defer server.Close()

	code, _, stderr := runForTest([]string{
		"plugin", "build", "astrbot-plugin-demo",
		"--version", "v1.2.4",
		"--ref", "main",
		"--changelog", "build notes",
		"--github-token", "github-token",
		"--credential-id", "repo-credential",
		"--server-url", server.URL,
		"--token", "admin-token",
	})
	if code != 0 {
		t.Fatalf("code=%d stderr=%s", code, stderr)
	}
	if body["version"] != "v1.2.4" ||
		body["ref"] != "main" ||
		body["changelog"] != "build notes" ||
		body["temporary_token"] != "github-token" ||
		body["credential_id"] != "repo-credential" {
		t.Fatalf("unexpected body: %v", body)
	}
}

func TestPluginBuildAllowsMetadataVersionDefault(t *testing.T) {
	pluginID := "11111111-1111-1111-1111-111111111111"
	var body map[string]any
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.Method == http.MethodGet && r.URL.Path == "/api/v1/admin/plugins":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"items": []map[string]any{{"id": pluginID, "plugin_key": "phimg"}},
				"total": 1, "page": 1, "page_size": 100,
			})
		case r.Method == http.MethodPost && r.URL.Path == "/api/v1/admin/plugins/"+pluginID+"/build":
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				t.Fatal(err)
			}
			_ = json.NewEncoder(w).Encode(map[string]any{"status": "queued"})
		default:
			t.Fatalf("unexpected request: %s %s", r.Method, r.URL.Path)
		}
	}))
	defer server.Close()

	code, _, stderr := runForTest([]string{
		"plugin", "build", "phimg",
		"--ref", "8eb1f0523b6f5accefa301369719792ca66e2611",
		"--changelog", "metadata version default",
		"--server-url", server.URL,
		"--token", "admin-token",
	})
	if code != 0 {
		t.Fatalf("code=%d stderr=%s", code, stderr)
	}
	if body["version"] != nil ||
		body["ref"] != "8eb1f0523b6f5accefa301369719792ca66e2611" ||
		body["changelog"] != "metadata version default" {
		t.Fatalf("unexpected body: %v", body)
	}
}

func TestAuthRegisterSolvesPOWAndSubmits(t *testing.T) {
	requests := []string{}
	var body map[string]any
	challengeID := "challenge-1"
	salt := "salt-1"
	difficulty := 8
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests = append(requests, r.Method+" "+r.URL.Path)
		switch {
		case r.Method == http.MethodGet && r.URL.Path == "/api/v1/auth/register/challenge":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"challenge_id": challengeID,
				"salt":         salt,
				"difficulty":   difficulty,
				"algorithm":    "sha256-leading-zero-bits",
				"expires_at":   "2026-07-08T12:00:00Z",
			})
		case r.Method == http.MethodPost && r.URL.Path == "/api/v1/auth/register":
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				t.Fatal(err)
			}
			nonce, _ := body["nonce"].(string)
			if !registerPOWValid(challengeID, salt, nonce, difficulty) {
				t.Fatalf("invalid nonce: %q", nonce)
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"status":  "active",
				"user_id": "user-1",
				"message": "registered",
			})
		default:
			t.Fatalf("unexpected request: %s %s", r.Method, r.URL.Path)
		}
	}))
	defer server.Close()

	code, stdout, stderr := runForTest([]string{
		"auth", "register",
		"--username", "alice",
		"--email", "alice@example.com",
		"--password", "strong-password",
		"--invite-code", "invite-1",
		"--pow-timeout", "5s",
		"--pow-workers", "2",
		"--server-url", server.URL,
	})
	if code != 0 {
		t.Fatalf("code=%d stderr=%s", code, stderr)
	}
	if strings.Join(requests, ",") != "GET /api/v1/auth/register/challenge,POST /api/v1/auth/register" {
		t.Fatalf("requests=%v", requests)
	}
	if body["username"] != "alice" ||
		body["email"] != "alice@example.com" ||
		body["password"] != "strong-password" ||
		body["invite_code"] != "invite-1" ||
		body["challenge_id"] != challengeID {
		t.Fatalf("unexpected body: %v", body)
	}
	if !strings.Contains(stdout, `"status": "active"`) {
		t.Fatalf("unexpected stdout: %s", stdout)
	}
}

func TestVersionDeleteSendsRequest(t *testing.T) {
	pluginID := "11111111-1111-1111-1111-111111111111"
	versionID := "22222222-2222-2222-2222-222222222222"
	seen := []string{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.Path)
		switch {
		case r.Method == http.MethodGet && r.URL.Path == "/api/v1/admin/plugins":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"items": []map[string]any{{"id": pluginID, "plugin_key": "astrbot-plugin-demo"}},
				"total": 1, "page": 1, "page_size": 100,
			})
		case r.Method == http.MethodGet && r.URL.Path == "/api/v1/admin/plugins/"+pluginID+"/versions":
			_ = json.NewEncoder(w).Encode([]map[string]any{{
				"id": versionID, "version": "v1.0.0",
			}})
		case r.Method == http.MethodDelete && r.URL.Path == "/api/v1/admin/plugins/"+pluginID+"/versions/"+versionID:
			_ = json.NewEncoder(w).Encode(map[string]string{"status": "deleted"})
		default:
			t.Fatalf("unexpected request: %s %s", r.Method, r.URL.Path)
		}
	}))
	defer server.Close()

	code, stdout, stderr := runForTest([]string{
		"plugin", "version", "delete", "astrbot-plugin-demo",
		"--version", "v1.0.0",
		"--yes",
		"--server-url", server.URL,
		"--token", "token",
	})
	if code != 0 {
		t.Fatalf("code=%d stderr=%s", code, stderr)
	}
	if !strings.Contains(stdout, `"status": "deleted"`) {
		t.Fatalf("unexpected stdout: %s", stdout)
	}
	want := []string{
		"GET /api/v1/admin/plugins",
		"GET /api/v1/admin/plugins/" + pluginID + "/versions",
		"DELETE /api/v1/admin/plugins/" + pluginID + "/versions/" + versionID,
	}
	if strings.Join(seen, ",") != strings.Join(want, ",") {
		t.Fatalf("seen=%v want=%v", seen, want)
	}
}

func runForTest(args []string) (int, string, string) {
	var stdout strings.Builder
	var stderr strings.Builder
	code := run(args, &stdout, &stderr)
	return code, stdout.String(), stderr.String()
}
