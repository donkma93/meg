namespace MegAccountManager.Models;

public sealed class Account
{
    public string Username { get; set; } = string.Empty;
    public List<string> Characters { get; set; } = new();
}
