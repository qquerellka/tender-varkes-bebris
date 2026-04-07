param(
    [string]$OutputDir = "",
    [int]$Seed = 42,
    [int]$Organizations = 12,
    [int]$UsersPerOrg = 8,
    [int]$Suppliers = 30,
    [int]$Items = 1200,
    [int]$SessionsPerUser = 32
)

$ErrorActionPreference = "Stop"

if ($Organizations -lt 1 -or $UsersPerOrg -lt 1 -or $Suppliers -lt 4 -or $Items -lt 100 -or $SessionsPerUser -lt 3) {
    throw "Invalid input sizes. Use Organizations>=1, UsersPerOrg>=1, Suppliers>=4, Items>=100, SessionsPerUser>=3."
}

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\data\synthetic"))
} else {
    $OutputDir = [System.IO.Path]::GetFullPath($OutputDir)
}

New-Item -Path $OutputDir -ItemType Directory -Force | Out-Null
Get-Random -SetSeed $Seed | Out-Null

function Pick-One {
    param([object[]]$Values)
    if (-not $Values -or $Values.Count -eq 0) {
        throw "Pick-One received empty list."
    }
    return $Values[(Get-Random -Minimum 0 -Maximum $Values.Count)]
}

function Pick-Many {
    param(
        [object[]]$Values,
        [int]$Count
    )
    if ($Count -le 0) {
        return @()
    }
    if ($Count -ge $Values.Count) {
        return @($Values)
    }
    return @($Values | Sort-Object { Get-Random } | Select-Object -First $Count)
}

function As-Json {
    param($Value)
    return ($Value | ConvertTo-Json -Depth 8 -Compress)
}

function Export-Table {
    param(
        [string]$FileName,
        [object[]]$Rows
    )
    $path = Join-Path $OutputDir $FileName
    $Rows | Export-Csv -Path $path -NoTypeInformation -Encoding UTF8
}

$now = [DateTime]::UtcNow

$categories = @(
    [pscustomobject]@{
        id = "cat_transport"
        name = "Transport"
        keywords = @("avtobus", "mikroavtobus", "passazhirskie perevozki", "arenda transporta", "logistika")
        synonyms = @{
            "avtobus" = @("passazhirskiy transport", "bus")
            "mikroavtobus" = @("minibus", "marshrutny transport")
            "logistika" = @("transportnaya logistika", "perevozki")
        }
        typos = @{
            "aftobus" = "avtobus"
            "mikroaftobus" = "mikroavtobus"
            "logstika" = "logistika"
        }
        attrA = @("city", "intercity", "school", "charter")
        attrB = @("rent", "fleet_support", "route_planning")
        priceMin = 160000
        priceMax = 1900000
    }
    [pscustomobject]@{
        id = "cat_it"
        name = "IT and Equipment"
        keywords = @("server", "setevoe oborudovanie", "noutbuk", "rabochaya stanciya", "kommutator")
        synonyms = @{
            "server" = @("servernoe oborudovanie", "compute node")
            "noutbuk" = @("laptop", "mobilnaya rabochaya stanciya")
            "kommutator" = @("switch", "setevoy kommutator")
        }
        typos = @{
            "serer" = "server"
            "noutbukk" = "noutbuk"
            "komutator" = "kommutator"
        }
        attrA = @("tower", "rack", "edge")
        attrB = @("supply", "maintenance", "monitoring")
        priceMin = 240000
        priceMax = 3800000
    }
    [pscustomobject]@{
        id = "cat_service"
        name = "Services"
        keywords = @("klining", "obsluzhivanie", "tehpodderzhka", "soprovozhdenie", "autsorsing")
        synonyms = @{
            "klining" = @("uborka pomescheniy", "cleaning service")
            "tehpodderzhka" = @("it support", "service desk")
            "obsluzhivanie" = @("ekspluataciya", "servis")
        }
        typos = @{
            "klinng" = "klining"
            "tehpodderzka" = "tehpodderzhka"
            "obsluzhvaniye" = "obsluzhivanie"
        }
        attrA = @("office", "it", "facility")
        attrB = @("monthly", "quarterly", "on_demand")
        priceMin = 90000
        priceMax = 1300000
    }
    [pscustomobject]@{
        id = "cat_office"
        name = "Office and Supplies"
        keywords = @("bumaga", "kanctovary", "kartridzh", "ofisnaya mebel", "printer")
        synonyms = @{
            "bumaga" = @("paper", "office paper")
            "kanctovary" = @("stationery", "office supplies")
            "kartridzh" = @("toner", "print consumables")
        }
        typos = @{
            "bumga" = "bumaga"
            "kanctovri" = "kanctovary"
            "katridzh" = "kartridzh"
        }
        attrA = @("a4", "a3", "ergonomic", "laser")
        attrB = @("bulk", "standard", "premium")
        priceMin = 20000
        priceMax = 460000
    }
)

$organizationsTable = New-Object System.Collections.Generic.List[object]
$users = New-Object System.Collections.Generic.List[object]
$suppliersTable = New-Object System.Collections.Generic.List[object]
$itemsTable = New-Object System.Collections.Generic.List[object]
$synonymsTable = New-Object System.Collections.Generic.List[object]
$spellsTable = New-Object System.Collections.Generic.List[object]
$purchaseHistoryTable = New-Object System.Collections.Generic.List[object]
$searchSessionsTable = New-Object System.Collections.Generic.List[object]
$searchEventsTable = New-Object System.Collections.Generic.List[object]
$queryRelevanceTable = New-Object System.Collections.Generic.List[object]
$userProfilesTable = New-Object System.Collections.Generic.List[object]
$orgProfilesTable = New-Object System.Collections.Generic.List[object]

$categoryById = @{}
foreach ($cat in $categories) {
    $categoryById[$cat.id] = $cat
}
$categoriesTable = @(
    $categories | ForEach-Object {
        [pscustomobject]@{
            id = $_.id
            name = $_.name
            parent_id = ""
        }
    }
)

$supplierPrefixes = @("OOO", "AO", "ZAO", "IP")
$supplierWordsA = @("Transit", "Infra", "Metro", "City", "Urban", "Smart", "Vector", "Delta", "Nova", "Astra")
$supplierWordsB = @("Systems", "Service", "Supply", "Logistics", "Trade", "Solutions", "Network", "Group")

for ($i = 1; $i -le $Suppliers; $i++) {
    $id = "sup_{0:d3}" -f $i
    $name = "{0} {1}{2} {3}" -f (Pick-One $supplierPrefixes), (Pick-One $supplierWordsA), $i, (Pick-One $supplierWordsB)
    $suppliersTable.Add([pscustomobject]@{
        id = $id
        name = $name
    })
}

$userPreferences = @{}
$userOrgMap = @{}

for ($orgIndex = 1; $orgIndex -le $Organizations; $orgIndex++) {
    $orgId = "org_{0:d3}" -f $orgIndex
    $organizationsTable.Add([pscustomobject]@{
        id = $orgId
        name = "Municipal Organization $orgIndex"
    })

    for ($userIndex = 1; $userIndex -le $UsersPerOrg; $userIndex++) {
        $globalUserIdx = (($orgIndex - 1) * $UsersPerOrg) + $userIndex
        $userId = "user_{0:d4}" -f $globalUserIdx
        $role = Pick-One @("customer", "analyst", "manager")
        $users.Add([pscustomobject]@{
            id = $userId
            organization_id = $orgId
            name = "User $globalUserIdx"
            role = $role
        })
        $preferredCategories = Pick-Many -Values $categories -Count 2 | ForEach-Object { $_.id }
        $userPreferences[$userId] = $preferredCategories
        $userOrgMap[$userId] = $orgId
    }
}

$itemNamePrefixes = @("Postavka", "Arenda", "Usluga", "Kompleksnaya postavka", "Tekhnicheskoe obsluzhivanie")
$itemNameSuffixes = @("dlya municipalnyh nuzhd", "dlya ofisov", "dlya infrastruktury", "s dostavkoy", "pod klyuch")

$itemsByCategory = @{}
$itemById = @{}
foreach ($cat in $categories) {
    $itemsByCategory[$cat.id] = New-Object System.Collections.Generic.List[string]
}

for ($i = 1; $i -le $Items; $i++) {
    $cat = Pick-One $categories
    $keyword = Pick-One $cat.keywords
    $title = "{0} {1} {2}" -f (Pick-One $itemNamePrefixes), $keyword, (Pick-One $itemNameSuffixes)
    $description = "Category $($cat.name). Product built around term '$keyword'."
    $supplier = Pick-One $suppliersTable
    $id = "ste_{0:d6}" -f $i
    $attributes = @{
        class = (Pick-One $cat.attrA)
        service = (Pick-One $cat.attrB)
        keyword = $keyword
    }

    $row = [pscustomobject]@{
        id = $id
        title = $title
        description = $description
        category_id = $cat.id
        supplier_id = $supplier.id
        attributes_json = (As-Json $attributes)
        status = "active"
        updated_at = $now.AddDays(-1 * (Get-Random -Minimum 0 -Maximum 120)).ToString("o")
    }

    $itemsTable.Add($row)
    $itemsByCategory[$cat.id].Add($id)
    $itemById[$id] = $row
}

$synIndex = 1
$spellIndex = 1
foreach ($cat in $categories) {
    foreach ($term in $cat.synonyms.Keys) {
        foreach ($synonym in $cat.synonyms[$term]) {
            $synonymsTable.Add([pscustomobject]@{
                id = "syn_{0:d4}" -f $synIndex
                term = $term
                synonym = $synonym
                weight = [math]::Round((Get-Random -Minimum 70 -Maximum 101) / 100.0, 2).ToString("0.00", [System.Globalization.CultureInfo]::InvariantCulture)
                source = "synthetic"
            })
            $synIndex++
        }
    }

    foreach ($wrong in $cat.typos.Keys) {
        $spellsTable.Add([pscustomobject]@{
            id = "spell_{0:d4}" -f $spellIndex
            wrong_term = $wrong
            correct_term = $cat.typos[$wrong]
            source = "synthetic"
        })
        $spellIndex++
    }
}

$purchaseIndex = 1
$sessionIndex = 1
$eventIndex = 1
$rankRowIndex = 1

$purchasesByUser = @{}
$sessionsByUser = @{}
$purchasesByOrg = @{}

foreach ($user in $users) {
    $purchasesByUser[$user.id] = New-Object System.Collections.Generic.List[object]
    $sessionsByUser[$user.id] = New-Object System.Collections.Generic.List[object]
    if (-not $purchasesByOrg.ContainsKey($user.organization_id)) {
        $purchasesByOrg[$user.organization_id] = New-Object System.Collections.Generic.List[object]
    }

    $preferredCategoryIds = $userPreferences[$user.id]
    $purchaseCount = Get-Random -Minimum 12 -Maximum 38

    for ($i = 0; $i -lt $purchaseCount; $i++) {
        $usePreferred = (Get-Random -Minimum 0 -Maximum 100) -lt 80
        if ($usePreferred) {
            $catId = Pick-One $preferredCategoryIds
        } else {
            $catId = (Pick-One $categories).id
        }

        $pool = $itemsByCategory[$catId]
        $steId = Pick-One $pool
        $catModel = $categoryById[$catId]
        $qty = Get-Random -Minimum 1 -Maximum 25
        $price = Get-Random -Minimum $catModel.priceMin -Maximum ($catModel.priceMax + 1)
        $purchasedAt = $now.AddDays(-1 * (Get-Random -Minimum 1 -Maximum 365)).AddMinutes(-1 * (Get-Random -Minimum 0 -Maximum 1440))

        $purchase = [pscustomobject]@{
            id = "ph_{0:d8}" -f $purchaseIndex
            user_id = $user.id
            organization_id = $user.organization_id
            ste_id = $steId
            quantity = [string]$qty
            price = [string]$price
            purchased_at = $purchasedAt.ToString("o")
        }
        $purchaseHistoryTable.Add($purchase)
        $purchasesByUser[$user.id].Add($purchase)
        $purchasesByOrg[$user.organization_id].Add($purchase)
        $purchaseIndex++
    }

    $sessionCount = $SessionsPerUser + (Get-Random -Minimum -5 -Maximum 6)
    if ($sessionCount -lt 3) {
        $sessionCount = 3
    }

    for ($s = 0; $s -lt $sessionCount; $s++) {
        $preferredCatId = Pick-One $preferredCategoryIds
        $catForQuery = $categoryById[$preferredCatId]
        $queryTerm = Pick-One $catForQuery.keywords
        $querySource = "base"

        $r = Get-Random -Minimum 0 -Maximum 100
        if ($r -lt 22 -and $catForQuery.synonyms.ContainsKey($queryTerm)) {
            $queryTerm = Pick-One $catForQuery.synonyms[$queryTerm]
            $querySource = "synonym"
        } elseif ($r -ge 22 -and $r -lt 40) {
            $matchingTypos = @()
            foreach ($k in $catForQuery.typos.Keys) {
                if ($catForQuery.typos[$k] -eq $queryTerm) {
                    $matchingTypos += $k
                }
            }
            if ($matchingTypos.Count -gt 0) {
                $queryTerm = Pick-One $matchingTypos
                $querySource = "typo"
            }
        }

        $query = "{0} {1}" -f $queryTerm, (Pick-One @("dlya zakupok", "moskva", "municipal", "portal postavshikov", ""))
        $query = $query.Trim()
        $normalized = $query.ToLowerInvariant()
        $createdAt = $now.AddDays(-1 * (Get-Random -Minimum 0 -Maximum 180)).AddMinutes(-1 * (Get-Random -Minimum 0 -Maximum 1440))
        $sessionId = "session_{0:d8}" -f $sessionIndex

        $sessionRow = [pscustomobject]@{
            id = $sessionId
            user_id = $user.id
            organization_id = $user.organization_id
            query = $query
            normalized_query = $normalized
            created_at = $createdAt.ToString("o")
        }
        $searchSessionsTable.Add($sessionRow)
        $sessionsByUser[$user.id].Add($sessionRow)

        $searchEventsTable.Add([pscustomobject]@{
            id = "event_{0:d9}" -f $eventIndex
            session_id = $sessionId
            user_id = $user.id
            organization_id = $user.organization_id
            event_type = "search_submitted"
            ste_id = ""
            payload_json = (As-Json @{ query_source = $querySource })
            created_at = $createdAt.ToString("o")
        })
        $eventIndex++

        $positivePool = @($itemsByCategory[$preferredCatId])
        $negativeCats = $categories | Where-Object { $_.id -ne $preferredCatId } | ForEach-Object { $_.id }
        $negativePool = @()
        foreach ($nc in (Pick-Many -Values $negativeCats -Count 2)) {
            $negativePool += $itemsByCategory[$nc]
        }
        $candidateIds = @()
        $candidateIds += (Pick-Many -Values $positivePool -Count 8)
        $candidateIds += (Pick-Many -Values $negativePool -Count 7)
        $candidateIds = @($candidateIds | Sort-Object { Get-Random })

        $clickChance = Get-Random -Minimum 0 -Maximum 100
        $clickedPos = if ($clickChance -lt 72) { Get-Random -Minimum 1 -Maximum 6 } else { -1 }
        $purchasePos = if ($clickedPos -gt 0 -and (Get-Random -Minimum 0 -Maximum 100) -lt 26) { $clickedPos } else { -1 }
        $favoritePos = if ($clickedPos -gt 0 -and (Get-Random -Minimum 0 -Maximum 100) -lt 38) { Get-Random -Minimum 1 -Maximum 8 } else { -1 }

        for ($pos = 1; $pos -le $candidateIds.Count; $pos++) {
            $itemId = $candidateIds[$pos - 1]
            $item = $itemById[$itemId]
            $label = 0
            $clicked = 0
            $purchased = 0
            $viewed = 0

            if ($item.category_id -eq $preferredCatId) {
                $label = 1
                $viewed = 1
            }
            if ($pos -eq $clickedPos) {
                $label = 2
                $clicked = 1
                $viewed = 1
            }
            if ($pos -eq $purchasePos) {
                $label = 3
                $clicked = 1
                $purchased = 1
                $viewed = 1
            }

            $queryRelevanceTable.Add([pscustomobject]@{
                row_id = $rankRowIndex
                session_id = $sessionId
                user_id = $user.id
                organization_id = $user.organization_id
                query = $query
                normalized_query = $normalized
                ste_id = $itemId
                position = $pos
                label = $label
                clicked = $clicked
                purchased = $purchased
                viewed = $viewed
                created_at = $createdAt.ToString("o")
            })
            $rankRowIndex++
        }

        if ($clickedPos -gt 0) {
            $clickedItem = $candidateIds[$clickedPos - 1]
            $searchEventsTable.Add([pscustomobject]@{
                id = "event_{0:d9}" -f $eventIndex
                session_id = $sessionId
                user_id = $user.id
                organization_id = $user.organization_id
                event_type = "result_clicked"
                ste_id = $clickedItem
                payload_json = (As-Json @{ position = $clickedPos })
                created_at = $createdAt.AddSeconds(8).ToString("o")
            })
            $eventIndex++
        }

        if ($favoritePos -gt 0) {
            $favoriteItem = $candidateIds[$favoritePos - 1]
            $searchEventsTable.Add([pscustomobject]@{
                id = "event_{0:d9}" -f $eventIndex
                session_id = $sessionId
                user_id = $user.id
                organization_id = $user.organization_id
                event_type = "favorite_added"
                ste_id = $favoriteItem
                payload_json = (As-Json @{ source = "search"; position = $favoritePos })
                created_at = $createdAt.AddSeconds(11).ToString("o")
            })
            $eventIndex++
        }

        if ($purchasePos -gt 0) {
            $boughtItem = $candidateIds[$purchasePos - 1]
            $searchEventsTable.Add([pscustomobject]@{
                id = "event_{0:d9}" -f $eventIndex
                session_id = $sessionId
                user_id = $user.id
                organization_id = $user.organization_id
                event_type = "purchase_completed"
                ste_id = $boughtItem
                payload_json = (As-Json @{ position = $purchasePos; source = "search" })
                created_at = $createdAt.AddSeconds(18).ToString("o")
            })
            $eventIndex++
        }

        $sessionIndex++
    }
}

$supplierNameById = @{}
foreach ($sup in $suppliersTable) {
    $supplierNameById[$sup.id] = $sup.name
}

$categoryNameById = @{}
foreach ($cat in $categories) {
    $categoryNameById[$cat.id] = $cat.name
}

foreach ($user in $users) {
    $userPurchases = @($purchaseHistoryTable | Where-Object { $_.user_id -eq $user.id })
    $userSessions = @($searchSessionsTable | Where-Object { $_.user_id -eq $user.id })

    $categoryCounts = @{}
    $supplierCounts = @{}
    foreach ($purchase in $userPurchases) {
        $ste = $itemById[$purchase.ste_id]
        if (-not $categoryCounts.ContainsKey($ste.category_id)) {
            $categoryCounts[$ste.category_id] = 0
        }
        if (-not $supplierCounts.ContainsKey($ste.supplier_id)) {
            $supplierCounts[$ste.supplier_id] = 0
        }
        $categoryCounts[$ste.category_id]++
        $supplierCounts[$ste.supplier_id]++
    }

    $topCategoryIds = @($categoryCounts.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 3 | ForEach-Object { $_.Key })
    if ($topCategoryIds.Count -eq 0) {
        $topCategoryIds = @($userPreferences[$user.id] | Select-Object -First 2)
    }
    $topCategories = @($topCategoryIds | ForEach-Object { $categoryNameById[$_] })

    $topSupplierIds = @($supplierCounts.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 3 | ForEach-Object { $_.Key })
    $topSuppliers = @($topSupplierIds | ForEach-Object { $supplierNameById[$_] })

    $recentSteIds = @(
        $userPurchases |
            Sort-Object { [DateTime]$_.purchased_at } -Descending |
            Select-Object -First 4 |
            ForEach-Object { $_.ste_id }
    )

    $queryCounts = @{}
    foreach ($session in $userSessions) {
        if (-not $queryCounts.ContainsKey($session.normalized_query)) {
            $queryCounts[$session.normalized_query] = 0
        }
        $queryCounts[$session.normalized_query]++
    }
    $popularQueries = @($queryCounts.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 8 | ForEach-Object { $_.Key })

    $userProfilesTable.Add([pscustomobject]@{
        user_id = $user.id
        organization_id = $user.organization_id
        top_categories_json = (As-Json $topCategories)
        recent_ste_ids_json = (As-Json $recentSteIds)
        top_suppliers_json = (As-Json $topSuppliers)
        popular_queries_json = (As-Json $popularQueries)
        updated_at = $now.ToString("o")
    })
}

foreach ($org in $organizationsTable) {
    $orgPurchases = @($purchaseHistoryTable | Where-Object { $_.organization_id -eq $org.id })
    $orgCategoryCounts = @{}
    $orgSteCounts = @{}

    foreach ($purchase in $orgPurchases) {
        $ste = $itemById[$purchase.ste_id]
        if (-not $orgCategoryCounts.ContainsKey($ste.category_id)) {
            $orgCategoryCounts[$ste.category_id] = 0
        }
        if (-not $orgSteCounts.ContainsKey($purchase.ste_id)) {
            $orgSteCounts[$purchase.ste_id] = 0
        }
        $orgCategoryCounts[$ste.category_id]++
        $orgSteCounts[$purchase.ste_id]++
    }

    $topOrgCategories = @(
        $orgCategoryCounts.GetEnumerator() |
            Sort-Object Value -Descending |
            Select-Object -First 3 |
            ForEach-Object { $categoryNameById[$_.Key] }
    )
    $topOrgSte = @(
        $orgSteCounts.GetEnumerator() |
            Sort-Object Value -Descending |
            Select-Object -First 8 |
            ForEach-Object { $_.Key }
    )

    $orgProfilesTable.Add([pscustomobject]@{
        organization_id = $org.id
        top_categories_json = (As-Json $topOrgCategories)
        popular_ste_ids_json = (As-Json $topOrgSte)
        updated_at = $now.ToString("o")
    })
}

Export-Table -FileName "organizations.csv" -Rows $organizationsTable
Export-Table -FileName "users.csv" -Rows $users
Export-Table -FileName "categories.csv" -Rows $categoriesTable
Export-Table -FileName "suppliers.csv" -Rows $suppliersTable
Export-Table -FileName "ste_items.csv" -Rows $itemsTable
Export-Table -FileName "synonyms.csv" -Rows $synonymsTable
Export-Table -FileName "spell_corrections.csv" -Rows $spellsTable
Export-Table -FileName "purchase_history.csv" -Rows $purchaseHistoryTable
Export-Table -FileName "search_sessions.csv" -Rows $searchSessionsTable
Export-Table -FileName "search_events.csv" -Rows $searchEventsTable
Export-Table -FileName "user_search_profiles.csv" -Rows $userProfilesTable
Export-Table -FileName "org_search_profiles.csv" -Rows $orgProfilesTable
Export-Table -FileName "query_relevance.csv" -Rows $queryRelevanceTable

Write-Host "Synthetic data generated."
Write-Host ("Output directory: {0}" -f $OutputDir)
Write-Host ("Rows: organizations={0}, users={1}, suppliers={2}, ste_items={3}" -f $organizationsTable.Count, $users.Count, $suppliersTable.Count, $itemsTable.Count)
Write-Host ("Rows: sessions={0}, events={1}, relevance={2}, purchases={3}" -f $searchSessionsTable.Count, $searchEventsTable.Count, $queryRelevanceTable.Count, $purchaseHistoryTable.Count)
