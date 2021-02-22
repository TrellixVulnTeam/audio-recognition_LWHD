# import matplotlib.pyplot as plt
from itertools import combinations
from sklearn.preprocessing import Normalizer
from collections import defaultdict
import scipy.io
import os
import requests
import numpy as np
import pandas as pd
import utils
import IPython.display as ipd
import matplotlib

import features as ft
import heapq
from sklearn.metrics.pairwise import pairwise_distances

matplotlib.use('TkAgg')
fma = utils.FreeMusicArchive(os.environ.get('FMA_KEY'))


# open file


# data = mat['X']
# data = Normalizer(norm='l2').fit_transform(data)
# data= data- data.mean(axis=0)
# classes = mat['X_class']

my_list = [1, 24, 21, 234, -8]

AUDIO_DIR = os.environ.get('data/fma_small')

tracks = utils.load('data/fma_metadata/tracks.csv')
genres = utils.load('data/fma_metadata/genres.csv')
features = utils.load('data/fma_metadata/features.csv')
echonest = utils.load('data/fma_metadata/echonest.csv')

# features = ''

n_vectors = 16


class LSH:
    def __init__(self, num_tables, hash_size, inp_dimensions):
        self.num_tables = num_tables
        self.hash_size = hash_size
        self.inp_dimensions = inp_dimensions
        self.hash_tables = list()
        for i in range(self.num_tables):
            self.hash_tables.append(
                HashTable(self.hash_size, self.inp_dimensions))

    def add(self, inp_vec):
        for table in self.hash_tables:
            table.add(inp_vec)

    def get(self, inp_vec, collision_ratio=0.5, probe=False):

        collisions_dict = {}
        for table in self.hash_tables:

            table_matches = table.get(inp_vec, probe)
            for point in table_matches:

                if point not in collisions_dict:
                    collisions_dict[point] = 0
                collisions_dict[point] = collisions_dict[point] + 1

        query_matches = []

        for c in collisions_dict:
            if collisions_dict[c] >= self.num_tables * collision_ratio:
                query_matches.append(c)

        return self.get_top_k(inp_vec, query_matches)

    def get_top_k(self, inp_vec, candidates, k=20):

        if not candidates:
            return None

        candidate_list = features.ix[candidates]['mfcc']

        ground_truths = tracks['track']['genre_top'].ix[candidates]

        distance = pairwise_distances(
            candidate_list, inp_vec, metric='euclidean').flatten()

        nearest_neighbours = pd.DataFrame({'id': candidates, 'genre': ground_truths, 'distance': distance}).sort_values(
            'distance').reset_index(drop=True)

        candidate_set_labels = nearest_neighbours.sort_values(
            by=['distance'], ascending=True)

        non_null = candidate_set_labels[candidate_set_labels['genre'].notnull(
        )]

        top = min(k, len(non_null))
        return non_null[:top]


class HashTable:
    def __init__(self, hash_size, inp_dimensions):
        self.hash_size = hash_size
        self.inp_dimensions = inp_dimensions
        self.hash_table = dict()
        self.projections = np.random.randn(inp_dimensions, hash_size)

    def add(self, inp_vec):

        keys = self.get_keys(inp_vec, False)
        keys_df = keys.to_frame(name="idx")
        track_hashes = keys_df.join(tracks['track'])

        for track in track_hashes.itertuples():

            # hash
            key = track[1]

            # song_id
            val = track[0]
            if key not in self.hash_table:
                self.hash_table[key] = []
            self.hash_table[key].append(val)

    def get_keys(self, inp_vec, is_probe):

        bin_bits = inp_vec.dot(self.projections) >= 0

        if (is_probe):
            print("BEFORE")
            print(len(bin_bits))
            bin_bits = self.get_probe_bins(bin_bits)
            print("AFTER")
            print(len(bin_bits))
            # print(bin_bits)

        powers_of_two = 1 << np.arange(self.hash_size - 1, -1, step=-1)
        decimal_keys = bin_bits.dot(powers_of_two)
        return decimal_keys

    def get_keys_cormode(self, inp_vec, k=2):

        print("AT CORMODE!!!!!")
        bin_bits = inp_vec.dot(self.projections)
# get top k columns for each row
# for each row:
    # create new key with flipped bit of one k coluns

        probed_keys = []

        for row in bin_bits.values:

            abs_idxs = [(abs(val), idx) for idx, val in enumerate(row)]

            smallest = heapq.nsmallest(k, abs_idxs)

            print("row ", row)
            print("smallest ", smallest)

            probed_keys.append(row)
            for pair in smallest:
                idx = pair[1]
                row_copy = row.copy()
                row_copy[idx] = row_copy[idx] * -1
                probed_keys.append(row_copy)

        probed_projections = pd.DataFrame(
            np.array(probed_keys), columns=bin_bits.columns)
        probed_bin_bits = (probed_projections) >= 0

        powers_of_two = 1 << np.arange(self.hash_size - 1, -1, step=-1)
        decimal_keys = probed_bin_bits.dot(powers_of_two)
        return decimal_keys


# return key

        # print(bin_bits)
#


    def get_probe_bins(self, bin_indices_bits, search_radius=1):

        for orig_bin in bin_indices_bits.values:

            p_bins = []
#
            for perturbed_idxs in combinations(range(self.hash_size), search_radius):

                idxs = list(perturbed_idxs)

                perturbed_query = orig_bin.copy()

                for idx in idxs:
                    perturbed_query[idx] = not perturbed_query[idx]

                p_bins.append(perturbed_query)

        return bin_indices_bits.append(pd.DataFrame(np.array(p_bins), columns=bin_indices_bits.columns))

    def get(self, inp_vec, probe):

        res = []
        if probe:
            bins = self.get_keys_cormode(inp_vec)
        else:
            bins = self.get_keys(inp_vec, False)

        for key in bins:

            if key in self.hash_table:
                # return self.hash_table[key]
                res.extend(self.hash_table[key])
        return res

    def majority(self, bin):

        # print("BIN", bin)

        genre_count = {}

        max_val = ""
        max_count = 0
        for g in bin:
            if g not in genre_count:
                genre_count[g] = 0
            genre_count[g] = genre_count[g] + 1

            # if (genre_count[g] > max_count):
            #     max_val = g
            #     max_count = genre_count[g]
        return genre_count

    def bar_chart(self, key, genres):

        genre_count = {}
        count = 0
        for g in genres:
            count = count + 1
            if g not in genre_count:
                genre_count[g] = 0
            genre_count[g] = genre_count[g] + 1

        max_val = ""
        val = 0
        for g in genre_count:

            if genre_count[g] > val:
                max_val = g
                val = genre_count[g]
        if (max_val == "Electronic"):
            print("key ", key, " values : ", genre_count,
                  " total: ", count, " \n \n \n")


lsh = LSH(1, 25, 140)
lsh.add(features['mfcc'])

# query_df = ft.compute_features(2)


# kate_nash_10s = ft.compute_features("./input_audio/kate_nash_10s.mp3")
# kate_nash_5s = ft.compute_features("./input_audio/kate_nash_5s.mp3")
# tinie = ft.compute_features("./input_audio/tinie.mp3")
# kate_nash_full = ft.compute_features("./input_audio/kate_nash_full.mp3")
# ariana_grande = ft.compute_features("./input_audio/ariana-grande.mp3")
# ludovico = ft.compute_features("./input_audio/ludovico_einaudi.mp3")
# liszt = ft.compute_features("./input_audio/franz_list.mp3")
# second = ft.compute_features("./input_audio/test.mp3")

# print("KATE NASHSES")
# print(kate_nash_10s)
# print("5sssss")
# print(kate_nash_5s)
# print("kate_nash_full")
# print(kate_nash_full)
# print("tinie")
# print(tinie)

# print("MY FEATURES")
# print(query_df)
# print("THEIRS")
# print(features.iloc[1:2])


# res = lsh.get(kate_nash_10s)
# print("KATE_NASH 10s")
# print(res)

# res_two = lsh.get(kate_nash_5s)
# print("KATE_NASH 5s")
# print(res_two)

# res_three = lsh.get(kate_nash_full)
# print("KATE_NASH FULL ")
# print(res_three)


# res_four = lsh.get(ariana_grande)
# print("ARIANA ")
# print(res_four)

# res_five = lsh.get(ludovico)
# print("LUDOVICO")
# print(res_five)

# res_six = lsh.get(liszt)
# print("LISZT")
# print(res_six)

dummy = lsh.get(features.iloc[1:2]['mfcc'], probe=False)
print("DUMMY - second song")
print(dummy)


cormode = lsh.get(features.iloc[1:2]['mfcc'], probe=True)
print("DUMMY - cormode!!!! song")
print(cormode)
# res_eight = lsh.get(second)
# print("my features - second song")
# print(res_eight)