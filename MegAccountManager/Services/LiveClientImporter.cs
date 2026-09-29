using MegAccountManager.Models;

namespace MegAccountManager.Services;

public sealed class ImportResult
{
    public int ClientsSeen { get; init; }
    public int AccountsCreated { get; init; }
    public int CharactersAdded { get; init; }
    public int CharactersAlreadyPresent { get; init; }
    public int ClientsWithoutAccount { get; init; }
    public IReadOnlyList<LiveClientInfo> Clients { get; init; } = Array.Empty<LiveClientInfo>();
}

public static class LiveClientImporter
{
    public static ImportResult MergeIntoAccounts(
        IList<Account> accounts,
        IEnumerable<LiveClientInfo> clients,
        bool createAccountWhenMissing = true)
    {
        var createdAccounts = 0;
        var addedCharacters = 0;
        var alreadyPresent = 0;
        var withoutAccount = 0;
        var clientList = clients.ToList();

        foreach (var client in clientList)
        {
            if (string.IsNullOrWhiteSpace(client.CharacterName))
            {
                continue;
            }

            if (string.IsNullOrWhiteSpace(client.AccountUsername))
            {
                withoutAccount++;
                continue;
            }

            var account = accounts.FirstOrDefault(a =>
                string.Equals(a.Username, client.AccountUsername, StringComparison.OrdinalIgnoreCase));

            if (account is null)
            {
                if (!createAccountWhenMissing)
                {
                    withoutAccount++;
                    continue;
                }

                account = new Account { Username = client.AccountUsername.Trim() };
                accounts.Add(account);
                createdAccounts++;
            }

            if (account.Characters.Any(c =>
                    string.Equals(c, client.CharacterName, StringComparison.OrdinalIgnoreCase)))
            {
                alreadyPresent++;
                continue;
            }

            account.Characters.Add(client.CharacterName.Trim());
            addedCharacters++;
        }

        return new ImportResult
        {
            ClientsSeen = clientList.Count,
            AccountsCreated = createdAccounts,
            CharactersAdded = addedCharacters,
            CharactersAlreadyPresent = alreadyPresent,
            ClientsWithoutAccount = withoutAccount,
            Clients = clientList
        };
    }
}
