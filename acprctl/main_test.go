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

func runForTest(args []string) (int, string, string) {
	var stdout strings.Builder
	var stderr strings.Builder
	code := run(args, &stdout, &stderr)
	return code, stdout.String(), stderr.String()
}
