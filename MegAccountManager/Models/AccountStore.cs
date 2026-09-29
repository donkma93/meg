using System.Text.Json;

namespace MegAccountManager.Models;

public sealed class AccountStore
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase
    };

    public string FilePath { get; }

    public AccountStore(string? filePath = null)
    {
        FilePath = filePath ?? Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "MegAccountManager",
            "accounts.json");
    }

    public List<Account> Load()
    {
        try
        {
            if (!File.Exists(FilePath))
            {
                return new List<Account>();
            }

            var json = File.ReadAllText(FilePath);
            if (string.IsNullOrWhiteSpace(json))
            {
                return new List<Account>();
            }

            return JsonSerializer.Deserialize<List<Account>>(json, JsonOptions) ?? new List<Account>();
        }
        catch (Exception ex)
        {
            throw new InvalidOperationException($"Không đọc được file dữ liệu:\n{FilePath}\n\n{ex.Message}", ex);
        }
    }

    public void Save(IEnumerable<Account> accounts)
    {
        var directory = Path.GetDirectoryName(FilePath);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }

        var ordered = accounts
            .OrderBy(a => a.Username, StringComparer.OrdinalIgnoreCase)
            .Select(a => new Account
            {
                Username = a.Username.Trim(),
                Characters = a.Characters
                    .Select(c => c.Trim())
                    .Where(c => !string.IsNullOrWhiteSpace(c))
                    .Distinct(StringComparer.OrdinalIgnoreCase)
                    .OrderBy(c => c, StringComparer.OrdinalIgnoreCase)
                    .ToList()
            })
            .Where(a => !string.IsNullOrWhiteSpace(a.Username))
            .ToList();

        var json = JsonSerializer.Serialize(ordered, JsonOptions);
        File.WriteAllText(FilePath, json);
    }
}
