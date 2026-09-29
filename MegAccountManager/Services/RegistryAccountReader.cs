using System.Text;
using System.Text.Json;
using Microsoft.Win32;
using MegAccountManager.Models;

namespace MegAccountManager.Services;

public sealed class RegistryAccountSnapshot
{
    public string? LastUsername { get; init; }
    public string? LastCharacter { get; init; }
    public string? LastServerLabel { get; init; }
    public IReadOnlyList<Account> Accounts { get; init; } = Array.Empty<Account>();
}

public static class RegistryAccountReader
{
    private const string RegistryPath = @"Software\MEGAMU\MEGAMU";
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    public static RegistryAccountSnapshot Read()
    {
        using var key = Registry.CurrentUser.OpenSubKey(RegistryPath);
        if (key is null)
        {
            return new RegistryAccountSnapshot();
        }

        var accountListJson = FindValueByPrefix(key, "AccountList_");
        var settingsJson = FindValueByPrefix(key, "Settings_h") ?? FindValueByPrefix(key, "Settings_");
        var accounts = ParseAccountList(accountListJson);

        string? lastUsername = null;
        string? lastCharacter = null;
        string? lastServerLabel = null;

        if (!string.IsNullOrWhiteSpace(settingsJson))
        {
            try
            {
                using var doc = JsonDocument.Parse(settingsJson);
                if (doc.RootElement.TryGetProperty("LastUsername", out var userProp))
                {
                    lastUsername = userProp.GetString();
                }

                if (doc.RootElement.TryGetProperty("LastCharacter", out var charProp))
                {
                    lastCharacter = charProp.GetString();
                }

                if (doc.RootElement.TryGetProperty("LastServerLabel", out var serverProp))
                {
                    lastServerLabel = serverProp.GetString();
                }
            }
            catch (JsonException)
            {
                // Ignore malformed settings blob.
            }
        }

        return new RegistryAccountSnapshot
        {
            Accounts = accounts,
            LastUsername = lastUsername,
            LastCharacter = lastCharacter,
            LastServerLabel = lastServerLabel
        };
    }

    public static void EnrichLiveClients(IEnumerable<LiveClientInfo> clients, RegistryAccountSnapshot snapshot)
    {
        var characterToAccount = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var account in snapshot.Accounts)
        {
            foreach (var character in account.Characters)
            {
                characterToAccount[character] = account.Username;
            }
        }

        foreach (var client in clients)
        {
            if (!string.IsNullOrWhiteSpace(client.AccountUsername))
            {
                continue;
            }

            if (characterToAccount.TryGetValue(client.CharacterName, out var username))
            {
                client.AccountUsername = username;
                client.Source = "registry:AccountList";
            }
        }
    }

    private static List<Account> ParseAccountList(string? json)
    {
        var result = new List<Account>();
        if (string.IsNullOrWhiteSpace(json))
        {
            return result;
        }

        try
        {
            using var doc = JsonDocument.Parse(json);
            if (!doc.RootElement.TryGetProperty("List", out var list) || list.ValueKind != JsonValueKind.Array)
            {
                return result;
            }

            foreach (var item in list.EnumerateArray())
            {
                var username = item.TryGetProperty("Username", out var userProp)
                    ? userProp.GetString()?.Trim()
                    : null;
                if (string.IsNullOrWhiteSpace(username))
                {
                    continue;
                }

                var account = new Account { Username = username };
                if (item.TryGetProperty("Characters", out var characters) &&
                    characters.ValueKind == JsonValueKind.Array)
                {
                    foreach (var character in characters.EnumerateArray())
                    {
                        var name = character.TryGetProperty("Name", out var nameProp)
                            ? nameProp.GetString()?.Trim()
                            : null;
                        if (!string.IsNullOrWhiteSpace(name) &&
                            !account.Characters.Contains(name, StringComparer.OrdinalIgnoreCase))
                        {
                            account.Characters.Add(name);
                        }
                    }
                }

                result.Add(account);
            }
        }
        catch (JsonException)
        {
            return result;
        }

        return result
            .OrderBy(a => a.Username, StringComparer.OrdinalIgnoreCase)
            .ToList();
    }

    private static string? FindValueByPrefix(RegistryKey key, string prefix)
    {
        foreach (var name in key.GetValueNames())
        {
            if (!name.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            // Prefer the large AccountList / Settings blobs over tiny unrelated keys.
            var text = ReadRegistryText(key, name);
            if (string.IsNullOrWhiteSpace(text))
            {
                continue;
            }

            if (prefix.StartsWith("AccountList", StringComparison.OrdinalIgnoreCase) &&
                text.Contains("\"Username\"", StringComparison.Ordinal))
            {
                return text;
            }

            if (prefix.StartsWith("Settings", StringComparison.OrdinalIgnoreCase) &&
                text.Contains("LastUsername", StringComparison.Ordinal))
            {
                return text;
            }

            if (text.StartsWith("{", StringComparison.Ordinal))
            {
                return text;
            }
        }

        return null;
    }

    private static string? ReadRegistryText(RegistryKey key, string name)
    {
        var value = key.GetValue(name);
        if (value is byte[] bytes && bytes.Length > 0)
        {
            // MEGAMU stores JSON as UTF-8 bytes in PlayerPrefs.
            var utf8 = Encoding.UTF8.GetString(bytes).TrimEnd('\0');
            if (utf8.Contains('{') || utf8.Contains('"'))
            {
                return utf8;
            }

            var utf16 = Encoding.Unicode.GetString(bytes).TrimEnd('\0');
            if (utf16.Contains('{') || utf16.Contains('"'))
            {
                return utf16;
            }

            return utf8;
        }

        if (value is string text)
        {
            return text.TrimEnd('\0');
        }

        return null;
    }
}
