package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
)

const (
	exitGeneral              = 1
	exitAuth                 = 2
	exitConfirmationRequired = 3
	exitNotFound             = 4
	exitWaitTimeout          = 5
	exitValidation           = 6
)

var uuidPattern = regexp.MustCompile(`^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$`)

type cliError struct {
	Message string
	Status  int
	Code    int
	Detail  any
}

func (e *cliError) Error() string {
	return e.Message
}

type globalFlags struct {
	ServerURL       string
	ServerURLSet    bool
	Username        string
	UsernameSet     bool
	Password        string
	PasswordSet     bool
	Token           string
	TokenSet        bool
	Config          string
	ConfigSet       bool
	Format          string
	FormatSet       bool
	Yes             bool
	Verbose         bool
	Timeout         string
	TimeoutSet      bool
	Wait            bool
	WaitInterval    string
	WaitIntervalSet bool
	WaitTimeout     string
	WaitTimeoutSet  bool
	Help            bool
}

type runtimeOptions struct {
	ConfigPath    string
	ConfigLoaded  bool
	ServerURL     string
	APIBaseURL    string
	Username      string
	Password      string
	Token         string
	OutputFormat  string
	Timeout       time.Duration
	Wait          bool
	WaitInterval  time.Duration
	WaitTimeout   time.Duration
	Yes           bool
	Verbose       bool
	RawConfig     map[string]string
	StoreNewToken bool
}

type client struct {
	options runtimeOptions
	token   string
	http    *http.Client
}

type optionSpec struct {
	HasValue bool
	Multiple bool
}

func main() {
	os.Exit(run(os.Args[1:], os.Stdout, os.Stderr))
}

func run(args []string, stdout io.Writer, stderr io.Writer) int {
	globals, remaining, err := parseGlobalFlags(args)
	if err != nil {
		emitError(stderr, &cliError{Message: err.Error(), Status: 400, Code: exitValidation})
		return exitValidation
	}
	if globals.Help {
		printHelp(stdout)
		return 0
	}
	options, cliErr := resolveRuntimeOptions(globals)
	if cliErr != nil {
		emitError(stderr, cliErr)
		return cliErr.Code
	}
	if len(remaining) == 0 {
		printHelp(stdout)
		return 0
	}

	var c *client
	if remaining[0] != "configure" {
		c, cliErr = newClient(options)
		if cliErr != nil {
			emitError(stderr, cliErr)
			return cliErr.Code
		}
	}

	result, cliErr := dispatch(remaining, options, c)
	if cliErr != nil {
		emitError(stderr, cliErr)
		return cliErr.Code
	}
	emitOutput(stdout, result, options.OutputFormat)
	return 0
}

func printHelp(w io.Writer) {
	fmt.Fprintln(w, "usage: acprctl [global flags] <command>")
	fmt.Fprintln(w)
	fmt.Fprintln(w, "commands:")
	fmt.Fprintln(w, "  configure")
	fmt.Fprintln(w, "  auth login")
	fmt.Fprintln(w, "  config list|set")
	fmt.Fprintln(w, "  cache refresh")
	fmt.Fprintln(w, "  stats")
	fmt.Fprintln(w, "  plugin list|show|submit|upload|update|delete|set-status|build|scan|version")
	fmt.Fprintln(w, "  review list|approve|publish|skip|disable|delete")
	fmt.Fprintln(w)
	fmt.Fprintln(w, "scan providers: clamav|virustotal|llm_agent|all")
}

func parseGlobalFlags(args []string) (globalFlags, []string, error) {
	var flags globalFlags
	remaining := make([]string, 0, len(args))

	valueFlags := map[string]func(string){
		"--server-url":    func(v string) { flags.ServerURL, flags.ServerURLSet = v, true },
		"-U":              func(v string) { flags.ServerURL, flags.ServerURLSet = v, true },
		"--username":      func(v string) { flags.Username, flags.UsernameSet = v, true },
		"-u":              func(v string) { flags.Username, flags.UsernameSet = v, true },
		"--password":      func(v string) { flags.Password, flags.PasswordSet = v, true },
		"-p":              func(v string) { flags.Password, flags.PasswordSet = v, true },
		"--token":         func(v string) { flags.Token, flags.TokenSet = v, true },
		"-t":              func(v string) { flags.Token, flags.TokenSet = v, true },
		"--config":        func(v string) { flags.Config, flags.ConfigSet = v, true },
		"-c":              func(v string) { flags.Config, flags.ConfigSet = v, true },
		"--format":        func(v string) { flags.Format, flags.FormatSet = v, true },
		"-f":              func(v string) { flags.Format, flags.FormatSet = v, true },
		"--timeout":       func(v string) { flags.Timeout, flags.TimeoutSet = v, true },
		"-T":              func(v string) { flags.Timeout, flags.TimeoutSet = v, true },
		"--wait-interval": func(v string) { flags.WaitInterval, flags.WaitIntervalSet = v, true },
		"-I":              func(v string) { flags.WaitInterval, flags.WaitIntervalSet = v, true },
		"--wait-timeout":  func(v string) { flags.WaitTimeout, flags.WaitTimeoutSet = v, true },
	}
	boolFlags := map[string]func(string) error{
		"--yes": func(v string) error {
			value, err := parseOptionalBool(v)
			flags.Yes = value
			return err
		},
		"-y": func(v string) error {
			value, err := parseOptionalBool(v)
			flags.Yes = value
			return err
		},
		"--verbose": func(v string) error {
			value, err := parseOptionalBool(v)
			flags.Verbose = value
			return err
		},
		"-v": func(v string) error {
			value, err := parseOptionalBool(v)
			flags.Verbose = value
			return err
		},
		"--wait": func(v string) error {
			value, err := parseOptionalBool(v)
			flags.Wait = value
			return err
		},
		"-W": func(v string) error {
			value, err := parseOptionalBool(v)
			flags.Wait = value
			return err
		},
		"--help": func(v string) error {
			value, err := parseOptionalBool(v)
			flags.Help = value
			return err
		},
		"-h": func(v string) error {
			value, err := parseOptionalBool(v)
			flags.Help = value
			return err
		},
	}

	for i := 0; i < len(args); i++ {
		arg := args[i]
		name, value, hasInline := splitFlagValue(arg)
		if setter, ok := valueFlags[name]; ok {
			if !hasInline {
				i++
				if i >= len(args) {
					return flags, nil, fmt.Errorf("%s requires a value", name)
				}
				value = args[i]
			}
			setter(value)
			continue
		}
		if setter, ok := boolFlags[name]; ok {
			if !hasInline {
				value = "true"
			}
			if err := setter(value); err != nil {
				return flags, nil, fmt.Errorf("invalid boolean for %s: %s", name, value)
			}
			continue
		}
		remaining = append(remaining, arg)
	}
	return flags, remaining, nil
}

func parseOptionalBool(value string) (bool, error) {
	if value == "" {
		return true, nil
	}
	return strconv.ParseBool(value)
}

func splitFlagValue(arg string) (string, string, bool) {
	if strings.HasPrefix(arg, "--") {
		if idx := strings.IndexByte(arg, '='); idx >= 0 {
			return arg[:idx], arg[idx+1:], true
		}
		return arg, "", false
	}
	return arg, "", false
}

func resolveRuntimeOptions(flags globalFlags) (runtimeOptions, *cliError) {
	configPath := defaultConfigPath()
	if flags.ConfigSet {
		configPath = expandPath(flags.Config)
	} else if value, ok := os.LookupEnv("ACPRCTL_CONFIG"); ok {
		configPath = expandPath(value)
	}

	rawConfig, configLoaded, err := readConfig(configPath)
	if err != nil {
		return runtimeOptions{}, &cliError{Message: err.Error(), Code: exitGeneral}
	}

	serverURL := chooseString(flags.ServerURL, flags.ServerURLSet, "ACPRCTL_SERVER_URL", rawConfig, "server_url", "")
	apiBaseURL := ""
	if serverURL != "" {
		apiBaseURL, err = normalizeAPIBaseURL(serverURL)
		if err != nil {
			return runtimeOptions{}, &cliError{Message: err.Error(), Status: 400, Code: exitValidation}
		}
	}

	format := chooseString(flags.Format, flags.FormatSet, "ACPRCTL_FORMAT", rawConfig, "format", "json")
	if format != "json" && format != "table" {
		return runtimeOptions{}, &cliError{Message: "format must be json or table", Status: 400, Code: exitValidation}
	}

	timeout, err := parseDuration(chooseString(flags.Timeout, flags.TimeoutSet, "ACPRCTL_TIMEOUT", rawConfig, "timeout", "30s"))
	if err != nil {
		return runtimeOptions{}, &cliError{Message: err.Error(), Status: 400, Code: exitValidation}
	}
	waitInterval, err := parseDuration(chooseString(flags.WaitInterval, flags.WaitIntervalSet, "ACPRCTL_WAIT_INTERVAL", rawConfig, "wait_interval", "3s"))
	if err != nil {
		return runtimeOptions{}, &cliError{Message: err.Error(), Status: 400, Code: exitValidation}
	}
	waitTimeout, err := parseDuration(chooseString(flags.WaitTimeout, flags.WaitTimeoutSet, "ACPRCTL_WAIT_TIMEOUT", rawConfig, "wait_timeout", "120s"))
	if err != nil {
		return runtimeOptions{}, &cliError{Message: err.Error(), Status: 400, Code: exitValidation}
	}

	return runtimeOptions{
		ConfigPath:    configPath,
		ConfigLoaded:  configLoaded,
		ServerURL:     serverURL,
		APIBaseURL:    apiBaseURL,
		Username:      chooseString(flags.Username, flags.UsernameSet, "ACPRCTL_USERNAME", rawConfig, "username", ""),
		Password:      chooseString(flags.Password, flags.PasswordSet, "ACPRCTL_PASSWORD", rawConfig, "password", ""),
		Token:         chooseString(flags.Token, flags.TokenSet, "ACPRCTL_TOKEN", rawConfig, "token", ""),
		OutputFormat:  format,
		Timeout:       timeout,
		Wait:          flags.Wait,
		WaitInterval:  waitInterval,
		WaitTimeout:   waitTimeout,
		Yes:           flags.Yes,
		Verbose:       flags.Verbose,
		RawConfig:     rawConfig,
		StoreNewToken: configLoaded,
	}, nil
}

func chooseString(flagValue string, flagSet bool, envKey string, config map[string]string, configKey string, fallback string) string {
	if flagSet {
		return flagValue
	}
	if value, ok := os.LookupEnv(envKey); ok {
		return value
	}
	if value, ok := config[configKey]; ok {
		return value
	}
	return fallback
}

func defaultConfigPath() string {
	if home := os.Getenv("XDG_CONFIG_HOME"); home != "" {
		return filepath.Join(expandPath(home), "acprctl", "config.yaml")
	}
	if home, err := os.UserHomeDir(); err == nil && home != "" {
		return filepath.Join(home, ".config", "acprctl", "config.yaml")
	}
	return filepath.Join(".config", "acprctl", "config.yaml")
}

func expandPath(path string) string {
	if path == "~" {
		if home, err := os.UserHomeDir(); err == nil {
			return home
		}
	}
	if strings.HasPrefix(path, "~/") {
		if home, err := os.UserHomeDir(); err == nil {
			return filepath.Join(home, path[2:])
		}
	}
	return path
}

func parseDuration(value string) (time.Duration, error) {
	value = strings.TrimSpace(value)
	if value == "" {
		return 0, errors.New("duration cannot be empty")
	}
	if seconds, err := strconv.ParseFloat(value, 64); err == nil {
		return time.Duration(seconds * float64(time.Second)), nil
	}
	duration, err := time.ParseDuration(value)
	if err != nil {
		return 0, fmt.Errorf("invalid duration: %s", value)
	}
	return duration, nil
}

func normalizeAPIBaseURL(serverURL string) (string, error) {
	value := strings.TrimRight(strings.TrimSpace(serverURL), "/")
	if value == "" {
		return "", errors.New("server URL is required")
	}
	parsed, err := url.Parse(value)
	if err != nil || parsed.Scheme == "" || parsed.Host == "" {
		return "", fmt.Errorf("invalid server URL: %s", serverURL)
	}
	if strings.HasSuffix(value, "/api/v1") {
		return value, nil
	}
	if strings.HasSuffix(value, "/api") {
		return value + "/v1", nil
	}
	return value + "/api/v1", nil
}

func readConfig(path string) (map[string]string, bool, error) {
	file, err := os.Open(path)
	if errors.Is(err, os.ErrNotExist) {
		return map[string]string{}, false, nil
	}
	if err != nil {
		return nil, false, fmt.Errorf("failed to read config file: %w", err)
	}
	defer file.Close()

	values := map[string]string{}
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		idx := strings.IndexByte(line, ':')
		if idx < 0 {
			return nil, true, fmt.Errorf("invalid config line: %s", line)
		}
		key := strings.TrimSpace(line[:idx])
		value := strings.TrimSpace(line[idx+1:])
		value = strings.Trim(value, `"'`)
		if key != "" {
			values[key] = value
		}
	}
	if err := scanner.Err(); err != nil {
		return nil, true, fmt.Errorf("failed to read config file: %w", err)
	}
	return values, true, nil
}

func writeConfig(path string, values map[string]string) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return fmt.Errorf("failed to create config directory: %w", err)
	}
	var buf bytes.Buffer
	keys := []string{"server_url", "username", "password", "token", "format", "timeout", "wait_interval", "wait_timeout"}
	for _, key := range keys {
		if value, ok := values[key]; ok {
			fmt.Fprintf(&buf, "%s: %s\n", key, yamlScalar(value))
		}
	}
	if err := os.WriteFile(path, buf.Bytes(), 0o600); err != nil {
		return fmt.Errorf("failed to write config file: %w", err)
	}
	return os.Chmod(path, 0o600)
}

func yamlScalar(value string) string {
	if value == "" {
		return `""`
	}
	if strings.ContainsAny(value, "\n#") || strings.HasPrefix(value, " ") || strings.HasSuffix(value, " ") {
		escaped := strings.ReplaceAll(value, `"`, `\"`)
		return `"` + escaped + `"`
	}
	return value
}

func newClient(options runtimeOptions) (*client, *cliError) {
	if options.APIBaseURL == "" {
		return nil, &cliError{
			Message: "server URL is required; use --server-url, ACPRCTL_SERVER_URL, or configure",
			Status:  400,
			Code:    exitValidation,
		}
	}
	return &client{
		options: options,
		token:   options.Token,
		http:    &http.Client{Timeout: options.Timeout},
	}, nil
}

func (c *client) login() (map[string]any, *cliError) {
	if c.options.Username == "" || c.options.Password == "" {
		return nil, &cliError{Message: "username and password are required for login", Status: 401, Code: exitAuth}
	}
	payload := map[string]string{"username": c.options.Username, "password": c.options.Password}
	result, err := c.request("POST", "/admin/login", nil, payload, false, true)
	if err != nil {
		return nil, err
	}
	token, _ := result["access_token"].(string)
	if token == "" {
		return nil, &cliError{Message: "login response did not include an access token", Status: 500, Code: exitGeneral, Detail: result}
	}
	c.token = token
	if c.options.StoreNewToken && c.options.Username != "" && c.options.Password != "" {
		updated := copyConfig(c.options.RawConfig)
		updated["token"] = token
		_ = writeConfig(c.options.ConfigPath, updated)
	}
	return result, nil
}

func (c *client) request(method string, path string, query url.Values, payload any, auth bool, retryAuth bool) (map[string]any, *cliError) {
	if auth && c.token == "" {
		if _, err := c.login(); err != nil {
			return nil, err
		}
	}
	var body io.Reader
	if payload != nil {
		data, err := json.Marshal(payload)
		if err != nil {
			return nil, &cliError{Message: err.Error(), Code: exitGeneral}
		}
		body = bytes.NewReader(data)
	}
	req, err := http.NewRequest(method, c.url(path, query), body)
	if err != nil {
		return nil, &cliError{Message: err.Error(), Code: exitGeneral}
	}
	if payload != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	if auth && c.token != "" {
		req.Header.Set("Authorization", "Bearer "+c.token)
	}
	c.debugf("%s %s", req.Method, req.URL.String())
	resp, err := c.http.Do(req)
	if err != nil {
		return nil, &cliError{Message: err.Error(), Code: exitGeneral}
	}
	defer resp.Body.Close()
	if resp.StatusCode == http.StatusUnauthorized && auth && retryAuth {
		if _, err := c.login(); err != nil {
			return nil, err
		}
		return c.request(method, path, query, payload, auth, false)
	}
	return decodeResponse(resp)
}

func (c *client) requestMultipart(path string, fields map[string]string, fileField string, filePath string) (map[string]any, *cliError) {
	return c.requestMultipartRetry(path, fields, fileField, filePath, true)
}

func (c *client) requestMultipartRetry(path string, fields map[string]string, fileField string, filePath string, retryAuth bool) (map[string]any, *cliError) {
	if c.token == "" {
		if _, err := c.login(); err != nil {
			return nil, err
		}
	}
	file, err := os.Open(filePath)
	if err != nil {
		return nil, &cliError{Message: "file not found: " + filePath, Status: 400, Code: exitValidation}
	}
	defer file.Close()

	var body bytes.Buffer
	writer := multipart.NewWriter(&body)
	for key, value := range fields {
		if err := writer.WriteField(key, value); err != nil {
			return nil, &cliError{Message: err.Error(), Code: exitGeneral}
		}
	}
	part, err := writer.CreateFormFile(fileField, filepath.Base(filePath))
	if err != nil {
		return nil, &cliError{Message: err.Error(), Code: exitGeneral}
	}
	if _, err := io.Copy(part, file); err != nil {
		return nil, &cliError{Message: err.Error(), Code: exitGeneral}
	}
	if err := writer.Close(); err != nil {
		return nil, &cliError{Message: err.Error(), Code: exitGeneral}
	}

	req, err := http.NewRequest("POST", c.url(path, nil), &body)
	if err != nil {
		return nil, &cliError{Message: err.Error(), Code: exitGeneral}
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())
	req.Header.Set("Authorization", "Bearer "+c.token)
	c.debugf("%s %s", req.Method, req.URL.String())
	resp, err := c.http.Do(req)
	if err != nil {
		return nil, &cliError{Message: err.Error(), Code: exitGeneral}
	}
	defer resp.Body.Close()
	if resp.StatusCode == http.StatusUnauthorized && retryAuth {
		if _, err := c.login(); err != nil {
			return nil, err
		}
		return c.requestMultipartRetry(path, fields, fileField, filePath, false)
	}
	return decodeResponse(resp)
}

func (c *client) url(path string, query url.Values) string {
	target := c.options.APIBaseURL + path
	if len(query) > 0 {
		target += "?" + query.Encode()
	}
	return target
}

func (c *client) debugf(format string, args ...any) {
	if c.options.Verbose {
		fmt.Fprintf(os.Stderr, "acprctl: "+format+"\n", args...)
	}
}

func decodeResponse(resp *http.Response) (map[string]any, *cliError) {
	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, &cliError{Message: err.Error(), Code: exitGeneral}
	}
	var decoded map[string]any
	if len(bytes.TrimSpace(data)) > 0 {
		if err := json.Unmarshal(data, &decoded); err != nil && resp.StatusCode < 400 {
			return nil, &cliError{Message: err.Error(), Status: resp.StatusCode, Code: exitGeneral}
		}
	}
	if resp.StatusCode >= 400 {
		return nil, apiError(resp.StatusCode, string(data), decoded)
	}
	if decoded == nil {
		decoded = map[string]any{}
	}
	return decoded, nil
}

func apiError(status int, raw string, decoded map[string]any) *cliError {
	message := http.StatusText(status)
	var detail any
	if decoded != nil {
		detail = decoded
		if value, ok := decoded["detail"]; ok {
			message = fmt.Sprint(value)
		} else if value, ok := decoded["error"]; ok {
			message = fmt.Sprint(value)
		}
	} else if strings.TrimSpace(raw) != "" {
		message = strings.TrimSpace(raw)
	}
	code := exitGeneral
	switch status {
	case http.StatusUnauthorized:
		code = exitAuth
	case http.StatusNotFound:
		code = exitNotFound
	case http.StatusBadRequest, http.StatusUnprocessableEntity:
		code = exitValidation
	}
	return &cliError{Message: message, Status: status, Code: code, Detail: detail}
}

func copyConfig(values map[string]string) map[string]string {
	copied := make(map[string]string, len(values))
	for key, value := range values {
		copied[key] = value
	}
	return copied
}

func dispatch(args []string, options runtimeOptions, c *client) (any, *cliError) {
	switch args[0] {
	case "configure":
		return handleConfigure(options)
	case "auth":
		if len(args) == 2 && args[1] == "login" {
			return c.login()
		}
	case "config":
		return dispatchConfig(args[1:], c)
	case "cache":
		if len(args) == 2 && args[1] == "refresh" {
			return c.request("POST", "/admin/cache/refresh", nil, nil, true, true)
		}
	case "stats":
		if len(args) == 1 {
			return c.request("GET", "/admin/stats", nil, nil, true, true)
		}
	case "plugin":
		return dispatchPlugin(args[1:], options, c)
	case "review":
		return dispatchReview(args[1:], options, c)
	}
	return nil, &cliError{Message: "unknown command: " + strings.Join(args, " "), Status: 400, Code: exitValidation}
}

func handleConfigure(options runtimeOptions) (map[string]any, *cliError) {
	if options.ServerURL == "" {
		return nil, &cliError{Message: "server URL is required for configure", Status: 400, Code: exitValidation}
	}
	data := copyConfig(options.RawConfig)
	data["server_url"] = options.ServerURL
	if options.Username != "" {
		data["username"] = options.Username
	}
	if options.Password != "" {
		data["password"] = options.Password
	}
	if options.Token != "" {
		data["token"] = options.Token
	}
	data["format"] = options.OutputFormat
	data["timeout"] = formatDuration(options.Timeout)
	data["wait_interval"] = formatDuration(options.WaitInterval)
	data["wait_timeout"] = formatDuration(options.WaitTimeout)

	tokenStored := data["token"] != ""
	if options.Username != "" && options.Password != "" {
		temp := options
		temp.StoreNewToken = false
		c, err := newClient(temp)
		if err != nil {
			return nil, err
		}
		login, err := c.login()
		if err != nil {
			return nil, err
		}
		data["token"], _ = login["access_token"].(string)
		tokenStored = data["token"] != ""
	}
	if err := writeConfig(options.ConfigPath, data); err != nil {
		return nil, &cliError{Message: err.Error(), Code: exitGeneral}
	}
	return map[string]any{
		"config_path":  options.ConfigPath,
		"server_url":   data["server_url"],
		"username":     data["username"],
		"token_stored": tokenStored,
	}, nil
}

func formatDuration(value time.Duration) string {
	if value%time.Second == 0 {
		return fmt.Sprintf("%ds", int(value/time.Second))
	}
	return value.String()
}

func dispatchConfig(args []string, c *client) (any, *cliError) {
	if len(args) == 0 {
		return nil, &cliError{Message: "config command is required", Status: 400, Code: exitValidation}
	}
	switch args[0] {
	case "list":
		if len(args) != 1 {
			return nil, &cliError{Message: "config list does not accept arguments", Status: 400, Code: exitValidation}
		}
		return c.request("GET", "/admin/config", nil, nil, true, true)
	case "set":
		opts, positionals, err := parseLocalOptions(args[1:], map[string]optionSpec{
			"key":   {HasValue: true, Multiple: true},
			"value": {HasValue: true, Multiple: true},
		})
		if err != nil {
			return nil, err
		}
		if len(positionals) > 0 {
			return nil, &cliError{Message: "config set does not accept positional arguments", Status: 400, Code: exitValidation}
		}
		keys := opts["key"]
		values := opts["value"]
		if len(keys) == 0 || len(keys) != len(values) {
			return nil, &cliError{Message: "--key and --value must be provided the same number of times", Status: 400, Code: exitValidation}
		}
		payload := map[string]any{"values": map[string]string{}}
		target := payload["values"].(map[string]string)
		for idx, key := range keys {
			target[key] = values[idx]
		}
		return c.request("PUT", "/admin/config", nil, payload, true, true)
	}
	return nil, &cliError{Message: "unknown config command: " + args[0], Status: 400, Code: exitValidation}
}

func dispatchPlugin(args []string, options runtimeOptions, c *client) (any, *cliError) {
	if len(args) == 0 {
		return nil, &cliError{Message: "plugin command is required", Status: 400, Code: exitValidation}
	}
	switch args[0] {
	case "list":
		opts, positionals, err := parseLocalOptions(args[1:], map[string]optionSpec{
			"status":    {HasValue: true},
			"q":         {HasValue: true},
			"page":      {HasValue: true},
			"page-size": {HasValue: true},
		})
		if err != nil {
			return nil, err
		}
		if len(positionals) > 0 {
			return nil, &cliError{Message: "plugin list does not accept positional arguments", Status: 400, Code: exitValidation}
		}
		query := url.Values{}
		addQuery(query, "status", last(opts["status"]))
		addQuery(query, "q", last(opts["q"]))
		addQueryDefault(query, "page", last(opts["page"]), "1")
		addQueryDefault(query, "page_size", last(opts["page-size"]), "20")
		return c.request("GET", "/admin/plugins", query, nil, true, true)
	case "show":
		opts, pos, err := parsePluginRefArgs(args[1:], nil)
		if err != nil {
			return nil, err
		}
		ref, err := pluginRef(opts, pos)
		if err != nil {
			return nil, err
		}
		return getPluginDetail(c, ref)
	case "submit":
		return handlePluginSubmit(args[1:], options, c)
	case "upload":
		return handlePluginUpload(args[1:], options, c)
	case "update":
		return handlePluginUpdate(args[1:], c)
	case "delete":
		return handlePluginDelete(args[1:], options, c)
	case "set-status":
		return handlePluginSetStatus(args[1:], c)
	case "build":
		return handlePluginBuild(args[1:], options, c)
	case "scan":
		return handlePluginScan(args[1:], options, c)
	case "version":
		return dispatchPluginVersion(args[1:], options, c)
	}
	return nil, &cliError{Message: "unknown plugin command: " + args[0], Status: 400, Code: exitValidation}
}

func handlePluginSubmit(args []string, options runtimeOptions, c *client) (any, *cliError) {
	opts, positionals, err := parseLocalOptions(args, map[string]optionSpec{
		"repo-url":   {HasValue: true},
		"version":    {HasValue: true},
		"ref":        {HasValue: true},
		"changelog":  {HasValue: true},
		"plugin-key": {HasValue: true},
	})
	if err != nil {
		return nil, err
	}
	if len(positionals) > 0 || last(opts["repo-url"]) == "" {
		return nil, &cliError{Message: "plugin submit requires --repo-url", Status: 400, Code: exitValidation}
	}
	payload := map[string]any{
		"repo_url":  last(opts["repo-url"]),
		"version":   nullableString(last(opts["version"])),
		"ref":       nullableString(last(opts["ref"])),
		"changelog": last(opts["changelog"]),
	}
	result, err := c.request("POST", "/admin/plugins", nil, payload, true, true)
	if err != nil {
		return nil, err
	}
	if options.Wait {
		waitRef := last(opts["plugin-key"])
		if waitRef == "" {
			waitRef, _ = result["plugin_id"].(string)
		}
		if waitRef == "" {
			waitRef = inferPluginKeyFromRepo(last(opts["repo-url"]))
		}
		if waitRef != "" {
			waitResult, err := waitForPluginVersion(c, waitRef, last(opts["version"]), options)
			if err != nil {
				return nil, err
			}
			result["wait"] = waitResult
		} else {
			result["wait"] = map[string]any{"status": "skipped", "reason": "no plugin id returned; pass --plugin-key to wait reliably"}
		}
	}
	return result, nil
}

func handlePluginUpload(args []string, options runtimeOptions, c *client) (any, *cliError) {
	opts, positionals, err := parseLocalOptions(args, map[string]optionSpec{"file": {HasValue: true}})
	if err != nil {
		return nil, err
	}
	file := last(opts["file"])
	if len(positionals) > 0 || file == "" {
		return nil, &cliError{Message: "plugin upload requires --file", Status: 400, Code: exitValidation}
	}
	result, err := c.requestMultipart("/admin/plugins/upload", nil, "file", file)
	if err != nil {
		return nil, err
	}
	if options.Wait {
		if pluginID, _ := result["plugin_id"].(string); pluginID != "" {
			if versionID, _ := result["version_id"].(string); versionID != "" {
				waitResult, err := waitForPluginVersion(c, pluginID, versionID, options)
				if err != nil {
					return nil, err
				}
				result["wait"] = waitResult
			}
		}
	}
	return result, nil
}

func handlePluginUpdate(args []string, c *client) (any, *cliError) {
	opts, pos, err := parsePluginRefArgs(args, map[string]optionSpec{
		"display-name":      {HasValue: true},
		"description":       {HasValue: true},
		"category":          {HasValue: true},
		"tags":              {HasValue: true},
		"support-platforms": {HasValue: true},
		"astrbot-version":   {HasValue: true},
	})
	if err != nil {
		return nil, err
	}
	ref, err := pluginRef(opts, pos)
	if err != nil {
		return nil, err
	}
	pluginID, err := resolvePluginID(c, ref)
	if err != nil {
		return nil, err
	}
	payload := map[string]any{}
	setString(payload, "display_name", last(opts["display-name"]))
	setString(payload, "description", last(opts["description"]))
	setString(payload, "category", last(opts["category"]))
	if value := last(opts["tags"]); value != "" {
		payload["tags"] = splitCSV(value)
	}
	if value := last(opts["support-platforms"]); value != "" {
		payload["support_platforms"] = splitCSV(value)
	}
	setString(payload, "astrbot_version", last(opts["astrbot-version"]))
	if len(payload) == 0 {
		return nil, &cliError{Message: "at least one update field is required", Status: 400, Code: exitValidation}
	}
	return c.request("PUT", "/admin/plugins/"+pluginID, nil, payload, true, true)
}

func handlePluginDelete(args []string, options runtimeOptions, c *client) (any, *cliError) {
	if !options.Yes {
		return nil, &cliError{Message: "destructive action requires --yes", Status: 400, Code: exitConfirmationRequired}
	}
	opts, pos, err := parsePluginRefArgs(args, nil)
	if err != nil {
		return nil, err
	}
	ref, err := pluginRef(opts, pos)
	if err != nil {
		return nil, err
	}
	pluginID, err := resolvePluginID(c, ref)
	if err != nil {
		return nil, err
	}
	return c.request("DELETE", "/admin/plugins/"+pluginID, nil, nil, true, true)
}

func handlePluginSetStatus(args []string, c *client) (any, *cliError) {
	opts, pos, err := parsePluginRefArgs(args, map[string]optionSpec{
		"status":        {HasValue: true},
		"review-status": {HasValue: true},
	})
	if err != nil {
		return nil, err
	}
	ref, err := pluginRef(opts, pos)
	if err != nil {
		return nil, err
	}
	status := last(opts["status"])
	if status == "" {
		return nil, &cliError{Message: "plugin set-status requires --status", Status: 400, Code: exitValidation}
	}
	pluginID, err := resolvePluginID(c, ref)
	if err != nil {
		return nil, err
	}
	payload := map[string]any{"status": status}
	setString(payload, "review_status", last(opts["review-status"]))
	return c.request("PUT", "/admin/plugins/"+pluginID+"/status", nil, payload, true, true)
}

func handlePluginBuild(args []string, options runtimeOptions, c *client) (any, *cliError) {
	opts, pos, err := parsePluginRefArgs(args, map[string]optionSpec{
		"version":   {HasValue: true},
		"ref":       {HasValue: true},
		"changelog": {HasValue: true},
	})
	if err != nil {
		return nil, err
	}
	ref, err := pluginRef(opts, pos)
	if err != nil {
		return nil, err
	}
	version := last(opts["version"])
	if version == "" {
		return nil, &cliError{Message: "plugin build requires --version", Status: 400, Code: exitValidation}
	}
	pluginID, err := resolvePluginID(c, ref)
	if err != nil {
		return nil, err
	}
	payload := map[string]any{"version": version, "changelog": last(opts["changelog"]), "ref": nullableString(last(opts["ref"]))}
	result, err := c.request("POST", "/admin/plugins/"+pluginID+"/build", nil, payload, true, true)
	if err != nil {
		return nil, err
	}
	if options.Wait {
		waitResult, err := waitForPluginVersion(c, pluginID, version, options)
		if err != nil {
			return nil, err
		}
		result["wait"] = waitResult
	}
	return result, nil
}

func handlePluginScan(args []string, options runtimeOptions, c *client) (any, *cliError) {
	opts, pos, err := parsePluginRefArgs(args, map[string]optionSpec{"version": {HasValue: true}})
	if err != nil {
		return nil, err
	}
	ref, err := pluginRef(opts, pos)
	if err != nil {
		return nil, err
	}
	version := last(opts["version"])
	if version == "" {
		return nil, &cliError{Message: "plugin scan requires --version", Status: 400, Code: exitValidation}
	}
	pluginID, err := resolvePluginID(c, ref)
	if err != nil {
		return nil, err
	}
	versionID, err := resolveVersionID(c, pluginID, version)
	if err != nil {
		return nil, err
	}
	query := url.Values{"version_id": []string{versionID}}
	result, err := c.request("POST", "/admin/plugins/"+pluginID+"/scan", query, nil, true, true)
	if err != nil {
		return nil, err
	}
	if options.Wait {
		waitResult, err := waitForScanProviders(c, pluginID, versionID, scanProvidersForWait("all"), options)
		if err != nil {
			return nil, err
		}
		result["wait"] = waitResult
	}
	return result, nil
}

func dispatchPluginVersion(args []string, options runtimeOptions, c *client) (any, *cliError) {
	if len(args) == 0 {
		return nil, &cliError{Message: "plugin version command is required", Status: 400, Code: exitValidation}
	}
	switch args[0] {
	case "list":
		opts, pos, err := parsePluginRefArgs(args[1:], nil)
		if err != nil {
			return nil, err
		}
		ref, err := pluginRef(opts, pos)
		if err != nil {
			return nil, err
		}
		pluginID, err := resolvePluginID(c, ref)
		if err != nil {
			return nil, err
		}
		return requestList(c, "/admin/plugins/"+pluginID+"/versions")
	case "upload":
		return handleVersionUpload(args[1:], options, c)
	case "set-latest":
		return handleVersionSetLatest(args[1:], c)
	case "set-status":
		return handleVersionSetStatus(args[1:], c)
	case "scan":
		return dispatchVersionScan(args[1:], options, c)
	}
	return nil, &cliError{Message: "unknown plugin version command: " + args[0], Status: 400, Code: exitValidation}
}

func handleVersionUpload(args []string, options runtimeOptions, c *client) (any, *cliError) {
	opts, pos, err := parsePluginRefArgs(args, map[string]optionSpec{
		"file":      {HasValue: true},
		"version":   {HasValue: true},
		"changelog": {HasValue: true},
	})
	if err != nil {
		return nil, err
	}
	ref, err := pluginRef(opts, pos)
	if err != nil {
		return nil, err
	}
	file := last(opts["file"])
	version := last(opts["version"])
	if file == "" || version == "" {
		return nil, &cliError{Message: "plugin version upload requires --file and --version", Status: 400, Code: exitValidation}
	}
	pluginID, err := resolvePluginID(c, ref)
	if err != nil {
		return nil, err
	}
	result, err := c.requestMultipart(
		"/admin/plugins/"+pluginID+"/versions/upload",
		map[string]string{"version": version, "changelog": last(opts["changelog"])},
		"file",
		file,
	)
	if err != nil {
		return nil, err
	}
	if options.Wait {
		if versionID, _ := result["version_id"].(string); versionID != "" {
			waitResult, err := waitForPluginVersion(c, pluginID, versionID, options)
			if err != nil {
				return nil, err
			}
			result["wait"] = waitResult
		}
	}
	return result, nil
}

func handleVersionSetLatest(args []string, c *client) (any, *cliError) {
	pluginID, versionID, err := resolvePluginAndVersion(c, args)
	if err != nil {
		return nil, err
	}
	return c.request("PUT", "/admin/plugins/"+pluginID+"/versions/"+versionID+"/latest", nil, map[string]bool{"is_latest": true}, true, true)
}

func handleVersionSetStatus(args []string, c *client) (any, *cliError) {
	opts, pos, err := parsePluginRefArgs(args, map[string]optionSpec{
		"version": {HasValue: true},
		"status":  {HasValue: true},
	})
	if err != nil {
		return nil, err
	}
	ref, err := pluginRef(opts, pos)
	if err != nil {
		return nil, err
	}
	version := last(opts["version"])
	status := last(opts["status"])
	if version == "" || status == "" {
		return nil, &cliError{Message: "plugin version set-status requires --version and --status", Status: 400, Code: exitValidation}
	}
	pluginID, err := resolvePluginID(c, ref)
	if err != nil {
		return nil, err
	}
	versionID, err := resolveVersionID(c, pluginID, version)
	if err != nil {
		return nil, err
	}
	return c.request("PUT", "/admin/plugins/"+pluginID+"/versions/"+versionID+"/status", nil, map[string]string{"status": status}, true, true)
}

func dispatchVersionScan(args []string, options runtimeOptions, c *client) (any, *cliError) {
	if len(args) == 0 {
		return nil, &cliError{Message: "plugin version scan command is required", Status: 400, Code: exitValidation}
	}
	switch args[0] {
	case "run", "skip":
		opts, pos, err := parsePluginRefArgs(args[1:], map[string]optionSpec{
			"version":  {HasValue: true},
			"provider": {HasValue: true},
		})
		if err != nil {
			return nil, err
		}
		ref, err := pluginRef(opts, pos)
		if err != nil {
			return nil, err
		}
		version := last(opts["version"])
		provider := last(opts["provider"])
		if version == "" || provider == "" {
			return nil, &cliError{Message: "plugin version scan " + args[0] + " requires --version and --provider", Status: 400, Code: exitValidation}
		}
		pluginID, err := resolvePluginID(c, ref)
		if err != nil {
			return nil, err
		}
		versionID, err := resolveVersionID(c, pluginID, version)
		if err != nil {
			return nil, err
		}
		result, err := c.request("POST", "/admin/plugins/"+pluginID+"/versions/"+versionID+"/scans/"+provider+"/"+args[0], nil, nil, true, true)
		if err != nil {
			return nil, err
		}
		if args[0] == "run" && options.Wait {
			waitResult, err := waitForScanProviders(c, pluginID, versionID, scanProvidersForWait(provider), options)
			if err != nil {
				return nil, err
			}
			result["wait"] = waitResult
		}
		return result, nil
	}
	return nil, &cliError{Message: "unknown plugin version scan command: " + args[0], Status: 400, Code: exitValidation}
}

func dispatchReview(args []string, options runtimeOptions, c *client) (any, *cliError) {
	if len(args) == 0 {
		return nil, &cliError{Message: "review command is required", Status: 400, Code: exitValidation}
	}
	switch args[0] {
	case "list":
		opts, positionals, err := parseLocalOptions(args[1:], map[string]optionSpec{
			"page":      {HasValue: true},
			"page-size": {HasValue: true},
		})
		if err != nil {
			return nil, err
		}
		if len(positionals) > 0 {
			return nil, &cliError{Message: "review list does not accept positional arguments", Status: 400, Code: exitValidation}
		}
		query := url.Values{"status": []string{"pending"}}
		addQueryDefault(query, "page", last(opts["page"]), "1")
		addQueryDefault(query, "page_size", last(opts["page-size"]), "20")
		return c.request("GET", "/admin/plugins", query, nil, true, true)
	case "approve":
		return setReviewStatus(args[1:], c, "active", "approved")
	case "publish":
		return publishReview(args[1:], c, "approved")
	case "skip":
		return publishReview(args[1:], c, "skipped")
	case "disable":
		return setReviewStatus(args[1:], c, "disabled", "")
	case "delete":
		return handlePluginDelete(args[1:], options, c)
	}
	return nil, &cliError{Message: "unknown review command: " + args[0], Status: 400, Code: exitValidation}
}

func setReviewStatus(args []string, c *client, status string, reviewStatus string) (any, *cliError) {
	opts, pos, err := parsePluginRefArgs(args, nil)
	if err != nil {
		return nil, err
	}
	ref, err := pluginRef(opts, pos)
	if err != nil {
		return nil, err
	}
	pluginID, err := resolvePluginID(c, ref)
	if err != nil {
		return nil, err
	}
	payload := map[string]any{"status": status}
	setString(payload, "review_status", reviewStatus)
	return c.request("PUT", "/admin/plugins/"+pluginID+"/status", nil, payload, true, true)
}

func publishReview(args []string, c *client, reviewStatus string) (any, *cliError) {
	opts, pos, err := parsePluginRefArgs(args, map[string]optionSpec{"version": {HasValue: true}})
	if err != nil {
		return nil, err
	}
	ref, err := pluginRef(opts, pos)
	if err != nil {
		return nil, err
	}
	pluginID, err := resolvePluginID(c, ref)
	if err != nil {
		return nil, err
	}
	versions, err := requestList(c, "/admin/plugins/"+pluginID+"/versions")
	if err != nil {
		return nil, err
	}
	version, err := selectPublishVersion(versions, last(opts["version"]))
	if err != nil {
		return nil, err
	}
	versionID := stringField(version, "id")
	result, err := c.request(
		"POST",
		"/admin/plugins/"+pluginID+"/versions/"+versionID+"/publish",
		nil,
		map[string]string{"review_status": reviewStatus},
		true,
		true,
	)
	if err != nil {
		return nil, err
	}
	return map[string]any{
		"publish": result,
		"version": version,
	}, nil
}

func parseLocalOptions(args []string, specs map[string]optionSpec) (map[string][]string, []string, *cliError) {
	values := map[string][]string{}
	positionals := []string{}
	for i := 0; i < len(args); i++ {
		arg := args[i]
		if arg == "--" {
			positionals = append(positionals, args[i+1:]...)
			break
		}
		if !strings.HasPrefix(arg, "--") {
			positionals = append(positionals, arg)
			continue
		}
		nameWithPrefix, value, hasInline := splitFlagValue(arg)
		name := strings.TrimPrefix(nameWithPrefix, "--")
		spec, ok := specs[name]
		if !ok {
			return nil, nil, &cliError{Message: "unknown flag: --" + name, Status: 400, Code: exitValidation}
		}
		if spec.HasValue {
			if !hasInline {
				i++
				if i >= len(args) {
					return nil, nil, &cliError{Message: "--" + name + " requires a value", Status: 400, Code: exitValidation}
				}
				value = args[i]
			}
		} else if !hasInline {
			value = "true"
		}
		if !spec.Multiple {
			values[name] = []string{value}
		} else {
			values[name] = append(values[name], value)
		}
	}
	return values, positionals, nil
}

func parsePluginRefArgs(args []string, extra map[string]optionSpec) (map[string][]string, []string, *cliError) {
	specs := map[string]optionSpec{"id": {HasValue: true}}
	for key, value := range extra {
		specs[key] = value
	}
	return parseLocalOptions(args, specs)
}

func pluginRef(opts map[string][]string, positionals []string) (string, *cliError) {
	if id := last(opts["id"]); id != "" {
		return id, nil
	}
	if len(positionals) > 0 {
		return positionals[0], nil
	}
	return "", &cliError{Message: "plugin reference or --id is required", Status: 400, Code: exitValidation}
}

func resolvePluginID(c *client, ref string) (string, *cliError) {
	if uuidPattern.MatchString(ref) {
		return ref, nil
	}
	query := url.Values{"q": []string{ref}, "page": []string{"1"}, "page_size": []string{"100"}}
	result, err := c.request("GET", "/admin/plugins", query, nil, true, true)
	if err != nil {
		return "", err
	}
	items, _ := result["items"].([]any)
	for _, item := range items {
		asMap, ok := item.(map[string]any)
		if ok && stringField(asMap, "plugin_key") == ref {
			return stringField(asMap, "id"), nil
		}
	}
	return "", &cliError{Message: "Plugin not found: " + ref, Status: 404, Code: exitNotFound}
}

func getPluginDetail(c *client, ref string) (map[string]any, *cliError) {
	pluginID, err := resolvePluginID(c, ref)
	if err != nil {
		return nil, err
	}
	return c.request("GET", "/admin/plugins/"+pluginID, nil, nil, true, true)
}

func resolveVersionID(c *client, pluginID string, versionRef string) (string, *cliError) {
	versions, err := requestList(c, "/admin/plugins/"+pluginID+"/versions")
	if err != nil {
		return "", err
	}
	version, err := findVersion(versions, versionRef)
	if err != nil {
		return "", err
	}
	return stringField(version, "id"), nil
}

func resolvePluginAndVersion(c *client, args []string) (string, string, *cliError) {
	opts, pos, err := parsePluginRefArgs(args, map[string]optionSpec{"version": {HasValue: true}})
	if err != nil {
		return "", "", err
	}
	ref, err := pluginRef(opts, pos)
	if err != nil {
		return "", "", err
	}
	version := last(opts["version"])
	if version == "" {
		return "", "", &cliError{Message: "--version is required", Status: 400, Code: exitValidation}
	}
	pluginID, err := resolvePluginID(c, ref)
	if err != nil {
		return "", "", err
	}
	versionID, err := resolveVersionID(c, pluginID, version)
	return pluginID, versionID, err
}

func requestList(c *client, path string) ([]map[string]any, *cliError) {
	return requestListRetry(c, path, true)
}

func requestListRetry(c *client, path string, retryAuth bool) ([]map[string]any, *cliError) {
	req, err := http.NewRequest("GET", c.url(path, nil), nil)
	if err != nil {
		return nil, &cliError{Message: err.Error(), Code: exitGeneral}
	}
	if c.token == "" {
		if _, loginErr := c.login(); loginErr != nil {
			return nil, loginErr
		}
	}
	req.Header.Set("Authorization", "Bearer "+c.token)
	c.debugf("%s %s", req.Method, req.URL.String())
	resp, httpErr := c.http.Do(req)
	if httpErr != nil {
		return nil, &cliError{Message: httpErr.Error(), Code: exitGeneral}
	}
	defer resp.Body.Close()
	if resp.StatusCode == http.StatusUnauthorized && retryAuth {
		if _, loginErr := c.login(); loginErr != nil {
			return nil, loginErr
		}
		return requestListRetry(c, path, false)
	}
	data, readErr := io.ReadAll(resp.Body)
	if readErr != nil {
		return nil, &cliError{Message: readErr.Error(), Code: exitGeneral}
	}
	if resp.StatusCode >= 400 {
		var decoded map[string]any
		_ = json.Unmarshal(data, &decoded)
		return nil, apiError(resp.StatusCode, string(data), decoded)
	}
	var raw []map[string]any
	if err := json.Unmarshal(data, &raw); err != nil {
		return nil, &cliError{Message: err.Error(), Status: resp.StatusCode, Code: exitGeneral}
	}
	return raw, nil
}

func findVersion(versions []map[string]any, versionRef string) (map[string]any, *cliError) {
	for _, version := range versions {
		if stringField(version, "id") == versionRef || stringField(version, "version") == versionRef {
			return version, nil
		}
	}
	return nil, &cliError{Message: "Version not found: " + versionRef, Status: 404, Code: exitNotFound}
}

func selectPublishVersion(versions []map[string]any, versionRef string) (map[string]any, *cliError) {
	if versionRef != "" {
		return findVersion(versions, versionRef)
	}
	for _, version := range versions {
		if stringField(version, "version_status") == "draft" {
			return version, nil
		}
	}
	if len(versions) > 0 {
		return versions[0], nil
	}
	return nil, &cliError{Message: "Plugin has no versions", Status: 404, Code: exitNotFound}
}

func waitForPluginVersion(c *client, pluginRef string, versionRef string, options runtimeOptions) (map[string]any, *cliError) {
	deadline := time.Now().Add(options.WaitTimeout)
	var lastDetail map[string]any
	var lastVersion map[string]any
	for {
		detail, err := getPluginDetail(c, pluginRef)
		if err != nil {
			if err.Code != exitNotFound || time.Now().After(deadline) {
				return nil, err
			}
		} else {
			lastDetail = detail
			version, found := pickWaitVersion(detail, versionRef)
			if found {
				lastVersion = version
				switch stringField(version, "build_status") {
				case "success":
					return map[string]any{"status": "success", "plugin": detail, "version": version}, nil
				case "failed":
					return nil, &cliError{
						Message: "Build failed",
						Code:    exitGeneral,
						Detail:  map[string]any{"plugin": detail, "version": version, "build_log": version["build_log"]},
					}
				}
			}
		}
		if time.Now().After(deadline) {
			return nil, &cliError{
				Message: "wait timeout",
				Code:    exitWaitTimeout,
				Detail:  map[string]any{"plugin": lastDetail, "version": lastVersion},
			}
		}
		time.Sleep(options.WaitInterval)
	}
}

func waitForScanProviders(c *client, pluginRef string, versionRef string, providers []string, options runtimeOptions) (map[string]any, *cliError) {
	deadline := time.Now().Add(options.WaitTimeout)
	var lastDetail map[string]any
	var lastVersion map[string]any
	for {
		detail, err := getPluginDetail(c, pluginRef)
		if err != nil {
			if err.Code != exitNotFound || time.Now().After(deadline) {
				return nil, err
			}
		} else {
			lastDetail = detail
			version, found := pickWaitVersion(detail, versionRef)
			if found {
				lastVersion = version
				if stringField(version, "build_status") == "failed" {
					return nil, &cliError{
						Message: "Build failed",
						Code:    exitGeneral,
						Detail:  map[string]any{"plugin": detail, "version": version, "build_log": version["build_log"]},
					}
				}
				done, scanErr := scanProvidersDone(version, providers)
				if scanErr != nil {
					scanErr.Detail = map[string]any{"plugin": detail, "version": version, "providers": providers}
					return nil, scanErr
				}
				if done {
					return map[string]any{
						"status":    "success",
						"plugin":    detail,
						"version":   version,
						"providers": resolvedScanProviders(version, providers),
					}, nil
				}
			}
		}
		if time.Now().After(deadline) {
			return nil, &cliError{
				Message: "wait timeout",
				Code:    exitWaitTimeout,
				Detail:  map[string]any{"plugin": lastDetail, "version": lastVersion, "providers": providers},
			}
		}
		time.Sleep(options.WaitInterval)
	}
}

func scanProvidersDone(version map[string]any, providers []string) (bool, *cliError) {
	scan := mapField(version, "scan")
	if len(scan) == 0 {
		return false, nil
	}
	resolvedProviders := resolvedScanProviders(version, providers)
	if len(resolvedProviders) == 0 {
		return false, nil
	}
	for _, provider := range resolvedProviders {
		result := mapField(scan, provider)
		if len(result) == 0 {
			return false, nil
		}
		mode := stringField(result, "mode")
		if mode == "" || mode == "pending" {
			return false, nil
		}
		if mode == "error" {
			return false, &cliError{Message: "Scan failed", Code: exitGeneral}
		}
		if mode == "skipped" {
			continue
		}
		passed, ok := boolField(result, "pass")
		if !ok {
			return false, nil
		}
		if !passed {
			return false, &cliError{Message: "Scan failed", Code: exitGeneral}
		}
	}
	return true, nil
}

func scanProvidersForWait(provider string) []string {
	if provider == "all" {
		return nil
	}
	return []string{provider}
}

func resolvedScanProviders(version map[string]any, providers []string) []string {
	if len(providers) > 0 {
		return providers
	}
	scan := mapField(version, "scan")
	resolved := make([]string, 0, len(scan))
	for key, value := range scan {
		if key == "scanned_at" {
			continue
		}
		if _, ok := value.(map[string]any); ok {
			resolved = append(resolved, key)
		}
	}
	sort.Strings(resolved)
	return resolved
}

func pickWaitVersion(detail map[string]any, versionRef string) (map[string]any, bool) {
	raw, _ := detail["versions"].([]any)
	versions := make([]map[string]any, 0, len(raw))
	for _, item := range raw {
		if asMap, ok := item.(map[string]any); ok {
			versions = append(versions, asMap)
		}
	}
	if versionRef != "" {
		version, err := findVersion(versions, versionRef)
		return version, err == nil
	}
	if len(versions) == 1 {
		return versions[0], true
	}
	for _, version := range versions {
		switch stringField(version, "build_status") {
		case "pending", "building", "scanning":
			return version, true
		}
	}
	if len(versions) > 0 {
		return versions[0], true
	}
	return nil, false
}

func inferPluginKeyFromRepo(repoURL string) string {
	parsed, err := url.Parse(repoURL)
	if err != nil {
		return ""
	}
	name := strings.TrimSuffix(filepath.Base(strings.TrimRight(parsed.Path, "/")), ".git")
	return strings.ReplaceAll(strings.ToLower(strings.TrimSpace(name)), "_", "-")
}

func addQuery(values url.Values, key string, value string) {
	if value != "" {
		values.Set(key, value)
	}
}

func addQueryDefault(values url.Values, key string, value string, fallback string) {
	if value == "" {
		value = fallback
	}
	values.Set(key, value)
}

func last(values []string) string {
	if len(values) == 0 {
		return ""
	}
	return values[len(values)-1]
}

func nullableString(value string) any {
	if value == "" {
		return nil
	}
	return value
}

func setString(payload map[string]any, key string, value string) {
	if value != "" {
		payload[key] = value
	}
}

func splitCSV(value string) []string {
	parts := strings.Split(value, ",")
	result := make([]string, 0, len(parts))
	for _, part := range parts {
		part = strings.TrimSpace(part)
		if part != "" {
			result = append(result, part)
		}
	}
	return result
}

func stringField(values map[string]any, key string) string {
	if value, ok := values[key].(string); ok {
		return value
	}
	return ""
}

func boolField(values map[string]any, key string) (bool, bool) {
	value, ok := values[key].(bool)
	return value, ok
}

func mapField(values map[string]any, key string) map[string]any {
	value, ok := values[key].(map[string]any)
	if !ok {
		return nil
	}
	return value
}

func emitOutput(w io.Writer, value any, format string) {
	if format == "table" {
		emitTable(w, value)
		return
	}
	encoder := json.NewEncoder(w)
	encoder.SetEscapeHTML(false)
	encoder.SetIndent("", "  ")
	_ = encoder.Encode(value)
}

func emitError(w io.Writer, err *cliError) {
	payload := map[string]any{"error": err.Message, "code": err.Code}
	if err.Status != 0 {
		payload["status"] = err.Status
	}
	if err.Detail != nil {
		payload["detail"] = err.Detail
	}
	emitOutput(w, payload, "json")
}

func emitTable(w io.Writer, value any) {
	rows := tableRows(value)
	if len(rows) == 0 {
		return
	}
	keys := tableKeys(rows)
	widths := map[string]int{}
	for _, key := range keys {
		widths[key] = len(key)
	}
	for _, row := range rows {
		for _, key := range keys {
			widths[key] = max(widths[key], len(fmt.Sprint(row[key])))
		}
	}
	for idx, key := range keys {
		if idx > 0 {
			fmt.Fprint(w, "  ")
		}
		fmt.Fprint(w, pad(key, widths[key]))
	}
	fmt.Fprintln(w)
	for idx, key := range keys {
		if idx > 0 {
			fmt.Fprint(w, "  ")
		}
		fmt.Fprint(w, strings.Repeat("-", widths[key]))
	}
	fmt.Fprintln(w)
	for _, row := range rows {
		for idx, key := range keys {
			if idx > 0 {
				fmt.Fprint(w, "  ")
			}
			fmt.Fprint(w, pad(fmt.Sprint(row[key]), widths[key]))
		}
		fmt.Fprintln(w)
	}
}

func tableRows(value any) []map[string]any {
	switch typed := value.(type) {
	case map[string]any:
		if items, ok := typed["items"].([]any); ok {
			rows := []map[string]any{}
			for _, item := range items {
				if row, ok := item.(map[string]any); ok {
					rows = append(rows, row)
				}
			}
			return rows
		}
		keys := make([]string, 0, len(typed))
		for key := range typed {
			keys = append(keys, key)
		}
		sort.Strings(keys)
		rows := make([]map[string]any, 0, len(keys))
		for _, key := range keys {
			rows = append(rows, map[string]any{"key": key, "value": typed[key]})
		}
		return rows
	case []map[string]any:
		return typed
	default:
		return nil
	}
}

func tableKeys(rows []map[string]any) []string {
	keys := []string{}
	for _, row := range rows {
		for key, value := range row {
			switch value.(type) {
			case map[string]any, []any:
				continue
			}
			if !contains(keys, key) {
				keys = append(keys, key)
			}
			if len(keys) >= 8 {
				return keys
			}
		}
	}
	sort.Strings(keys)
	return keys
}

func contains(values []string, target string) bool {
	for _, value := range values {
		if value == target {
			return true
		}
	}
	return false
}

func pad(value string, width int) string {
	if len(value) >= width {
		return value
	}
	return value + strings.Repeat(" ", width-len(value))
}
