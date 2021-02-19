def deleteDup(lst):
    if len(lst) > 3:
        if lst[-1] == lst[-3]:
            lst = lst[: len(lst) - 2]

            return lst
    return lst